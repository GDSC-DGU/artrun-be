package com.artrun.server.service;

import com.artrun.server.common.BusinessException;
import com.artrun.server.common.ErrorCode;
import com.artrun.server.dto.AnchorPoint;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.cloud.vertexai.VertexAI;
import com.google.cloud.vertexai.api.GenerateContentResponse;
import com.google.cloud.vertexai.generativemodel.GenerativeModel;
import com.google.cloud.vertexai.generativemodel.ContentMaker;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
public class ShapeEngineService {

    private final String projectId;
    private final String location;
    private final String modelName;
    private final ObjectMapper objectMapper;

    public ShapeEngineService(
            @Value("${gcp.project-id:artrun-project}") String projectId,
            @Value("${gcp.location:us-central1}") String location,
            @Value("${gcp.vertex-ai.model:gemini-2.0-flash}") String modelName,
            ObjectMapper objectMapper) {
        this.projectId = projectId;
        this.location = location;
        this.modelName = modelName;
        this.objectMapper = objectMapper;
    }

    public List<AnchorPoint> generateShapeCoordinates(String requestText, String shapeType) {
        log.info("Generating shape coordinates: requestText={}, shapeType={}", requestText, shapeType);

        String prompt = buildPrompt(requestText, shapeType);

        try (VertexAI vertexAI = new VertexAI(projectId, location)) {
            GenerativeModel model = new GenerativeModel(modelName, vertexAI);
            GenerateContentResponse response = model.generateContent(ContentMaker.fromString(prompt));

            String responseText = response.getCandidates(0)
                    .getContent()
                    .getParts(0)
                    .getText();

            return parseAnchorPoints(responseText);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("AI API call failed", e);
            throw new BusinessException(ErrorCode.AI_API_ERROR, "AI 도형 생성 실패: " + e.getMessage());
        }
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
