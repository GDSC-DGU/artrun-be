package com.artrun.server.service;

import com.artrun.server.domain.RunRecord;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.time.format.DateTimeFormatter;

@Slf4j
@Service
@RequiredArgsConstructor
public class ShareCardService {

    private static final int W = 800;
    private static final int H = 450;
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy.MM.dd");

    private final S3Service s3Service;

    public String generateAndUpload(RunRecord record) {
        try {
            byte[] imageBytes = generateCard(record);
            String key = "share-cards/" + record.getId() + ".png";
            return s3Service.upload(key, imageBytes, "image/png");
        } catch (Exception e) {
            log.error("Share card generation failed for record {}: {}", record.getId(), e.getMessage());
            return null;
        }
    }

    private byte[] generateCard(RunRecord record) throws Exception {
        BufferedImage img = new BufferedImage(W, H, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);

        // 배경 그라데이션
        GradientPaint gradient = new GradientPaint(0, 0, new Color(30, 30, 60), W, H, new Color(60, 20, 80));
        g.setPaint(gradient);
        g.fillRect(0, 0, W, H);

        // 타이틀
        g.setColor(new Color(180, 140, 255));
        g.setFont(new Font("SansSerif", Font.BOLD, 28));
        g.drawString("ArtRun", 50, 60);

        // 날짜
        g.setColor(new Color(200, 200, 200));
        g.setFont(new Font("SansSerif", Font.PLAIN, 18));
        String date = record.getCreatedAt() != null ? record.getCreatedAt().format(DATE_FMT) : "";
        g.drawString(date, 50, 95);

        // 구분선
        g.setColor(new Color(120, 80, 200));
        g.setStroke(new BasicStroke(2));
        g.drawLine(50, 115, W - 50, 115);

        // 거리
        double km = record.getTotalDistanceMeters() / 1000.0;
        g.setColor(Color.WHITE);
        g.setFont(new Font("SansSerif", Font.BOLD, 72));
        g.drawString(String.format("%.2f", km), 50, 220);
        g.setFont(new Font("SansSerif", Font.PLAIN, 24));
        g.setColor(new Color(180, 180, 180));
        g.drawString("km", 50, 255);

        // 시간 / 페이스
        int totalSec = record.getTotalTimeSeconds() != null ? record.getTotalTimeSeconds() : 0;
        String timeStr = String.format("%02d:%02d:%02d", totalSec / 3600, (totalSec % 3600) / 60, totalSec % 60);
        double paceSecPerKm = km > 0 ? (totalSec / km) : 0;
        String paceStr = String.format("%d'%02d\"", (int)(paceSecPerKm / 60), (int)(paceSecPerKm % 60));

        g.setColor(Color.WHITE);
        g.setFont(new Font("SansSerif", Font.BOLD, 36));
        g.drawString(timeStr, 50, 340);
        g.setFont(new Font("SansSerif", Font.PLAIN, 18));
        g.setColor(new Color(180, 180, 180));
        g.drawString("시간", 50, 370);

        g.setFont(new Font("SansSerif", Font.BOLD, 36));
        g.setColor(Color.WHITE);
        g.drawString(paceStr, 350, 340);
        g.setFont(new Font("SansSerif", Font.PLAIN, 18));
        g.setColor(new Color(180, 180, 180));
        g.drawString("/km 페이스", 350, 370);

        // 하단 구분선
        g.setColor(new Color(120, 80, 200));
        g.setStroke(new BasicStroke(2));
        g.drawLine(50, 400, W - 50, 400);

        g.setFont(new Font("SansSerif", Font.PLAIN, 16));
        g.setColor(new Color(150, 150, 150));
        g.drawString("artrun.app", 50, 430);

        g.dispose();

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ImageIO.write(img, "PNG", out);
        return out.toByteArray();
    }
}
