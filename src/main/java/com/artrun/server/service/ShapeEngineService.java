package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.dto.AnchorPoint;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.util.List;

@Slf4j
@Service
public class ShapeEngineService {

    private final String apiKey;
    private final String modelName;
    private final ObjectMapper objectMapper;
    private final RestClient restClient;

    public ShapeEngineService(
            @Value("${gemini.api-key:}") String apiKey,
            @Value("${gemini.model:gemini-2.0-flash}") String modelName,
            ObjectMapper objectMapper) {
        this.apiKey = apiKey;
        this.modelName = modelName;
        this.objectMapper = objectMapper;
        this.restClient = RestClient.create();
    }

    public List<AnchorPoint> generateShapeCoordinates(String requestText, String shapeType) {
        log.info("Generating shape coordinates: requestText={}, shapeType={}", requestText, shapeType);

        if (apiKey == null || apiKey.isBlank()) {
            log.warn("Gemini API key not set, using stub shape for '{}'", shapeType);
            return getStubShape(shapeType);
        }

        try {
            return callGeminiApi(requestText, shapeType);
        } catch (Exception e) {
            log.warn("Gemini API failed, falling back to stub shape: {}", e.getMessage());
            return getStubShape(shapeType);
        }
    }

    private List<AnchorPoint> callGeminiApi(String requestText, String shapeType) {
        String prompt = buildPrompt(requestText, shapeType);
        String url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
                .formatted(modelName, apiKey);

        String requestBody = objectMapper.writeValueAsString(
                objectMapper.createObjectNode()
                        .set("contents", objectMapper.createArrayNode()
                                .add(objectMapper.createObjectNode()
                                        .set("parts", objectMapper.createArrayNode()
                                                .add(objectMapper.createObjectNode()
                                                        .put("text", prompt))))));

        String responseBody = restClient.post()
                .uri(url)
                .contentType(MediaType.APPLICATION_JSON)
                .body(requestBody)
                .retrieve()
                .body(String.class);

        JsonNode root = objectMapper.readTree(responseBody);
        String responseText = root.path("candidates").path(0)
                .path("content").path("parts").path(0)
                .path("text").asText();

        log.debug("Gemini response: {}", responseText);
        return parseAnchorPoints(responseText);
    }

    private List<AnchorPoint> getStubShape(String shapeType) {
        return switch (shapeType.toLowerCase()) {
            case "heart" -> List.of(
                    new AnchorPoint(0.0, 0.4), new AnchorPoint(-0.2, 0.8), new AnchorPoint(-0.5, 0.9),
                    new AnchorPoint(-0.8, 0.7), new AnchorPoint(-0.9, 0.3), new AnchorPoint(-0.7, -0.1),
                    new AnchorPoint(-0.4, -0.5), new AnchorPoint(0.0, -0.9),
                    new AnchorPoint(0.4, -0.5), new AnchorPoint(0.7, -0.1), new AnchorPoint(0.9, 0.3),
                    new AnchorPoint(0.8, 0.7), new AnchorPoint(0.5, 0.9), new AnchorPoint(0.2, 0.8),
                    new AnchorPoint(0.0, 0.4));
            case "star" -> List.of(
                    new AnchorPoint(0.0, 1.0), new AnchorPoint(-0.22, 0.31), new AnchorPoint(-0.95, 0.31),
                    new AnchorPoint(-0.36, -0.12), new AnchorPoint(-0.59, -0.81),
                    new AnchorPoint(0.0, -0.38), new AnchorPoint(0.59, -0.81),
                    new AnchorPoint(0.36, -0.12), new AnchorPoint(0.95, 0.31),
                    new AnchorPoint(0.22, 0.31), new AnchorPoint(0.0, 1.0));
            default -> List.of( // circle
                    new AnchorPoint(0.0, 1.0), new AnchorPoint(-0.38, 0.92), new AnchorPoint(-0.71, 0.71),
                    new AnchorPoint(-0.92, 0.38), new AnchorPoint(-1.0, 0.0), new AnchorPoint(-0.92, -0.38),
                    new AnchorPoint(-0.71, -0.71), new AnchorPoint(-0.38, -0.92), new AnchorPoint(0.0, -1.0),
                    new AnchorPoint(0.38, -0.92), new AnchorPoint(0.71, -0.71), new AnchorPoint(0.92, -0.38),
                    new AnchorPoint(1.0, 0.0), new AnchorPoint(0.92, 0.38), new AnchorPoint(0.71, 0.71),
                    new AnchorPoint(0.38, 0.92), new AnchorPoint(0.0, 1.0));
        };
    }

    private String buildPrompt(String requestText, String shapeType) {
        return """
                You are a shape coordinate generator for a GPS art running application.

                User request: "%s"
                Shape type: "%s"

                Generate a closed polygon shape as a list of 2D anchor points.
                The shape should be recognizable as the requested form.

                Rules:
                - Return ONLY a JSON array of {x, y} coordinates
                - Use a normalized coordinate system where x and y range from -1.0 to 1.0
                - The first and last points must be the same (closed polygon)
                - Use 15-30 anchor points for good shape definition
                - The shape should be centered around origin (0, 0)

                Example output format:
                [{"x": 0.0, "y": 1.0}, {"x": 0.5, "y": 0.5}, ..., {"x": 0.0, "y": 1.0}]

                Return ONLY the JSON array, no other text.
                """.formatted(requestText, shapeType);
    }

    private List<AnchorPoint> parseAnchorPoints(String responseText) {
        try {
            String json = responseText.strip();
            if (json.startsWith("```")) {
                json = json.replaceAll("```json?\\s*", "").replaceAll("```\\s*$", "").strip();
            }
            List<AnchorPoint> points = objectMapper.readValue(json, new TypeReference<>() {});
            if (points.size() < 3) {
                throw new BusinessException(ErrorCode.AI_API_ERROR, "생성된 좌표가 너무 적습니다.");
            }
            return points;
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Failed to parse AI response: {}", responseText, e);
            throw new BusinessException(ErrorCode.AI_API_ERROR, "AI 응답 파싱 실패");
        }
    }
}
