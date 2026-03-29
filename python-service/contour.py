# python-service/contour.py
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 창 없이 파일로 저장
import matplotlib.pyplot as plt

# 테스트용 거북이 실루엣 이미지를 코드로 생성
img = np.zeros((400, 600), dtype=np.uint8)
cv2.ellipse(img, (300, 200), (160, 120), 0, 0, 360, 255, -1)  # 몸통
cv2.ellipse(img, (300, 100), (50, 40),  0, 0, 360, 255, -1)   # 머리
cv2.ellipse(img, (160, 160), (40, 25), -30, 0, 360, 255, -1)  # 왼앞발
cv2.ellipse(img, (440, 160), (40, 25),  30, 0, 360, 255, -1)  # 오른앞발
cv2.ellipse(img, (180, 280), (35, 22), -20, 0, 360, 255, -1)  # 왼뒷발
cv2.ellipse(img, (420, 280), (35, 22),  20, 0, 360, 255, -1)  # 오른뒷발

# 외곽선 추출
contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
main_contour = max(contours, key=cv2.contourArea)
epsilon = 0.001 * cv2.arcLength(main_contour, True)
approx = cv2.approxPolyDP(main_contour, epsilon, True)

# 결과 이미지 저장
result = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
cv2.drawContours(result, [approx], -1, (0, 255, 0), 3)

# 좌표 점도 표시
for pt in approx:
    cv2.circle(result, tuple(pt[0]), 5, (0, 0, 255), -1)

plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1)
plt.imshow(img, cmap='gray')
plt.title("원본 실루엣")
plt.axis('off')

plt.subplot(1, 2, 2)
plt.imshow(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
plt.title(f"추출된 외곽선 (좌표 {len(approx)}개)")
plt.axis('off')

plt.tight_layout()
plt.savefig("/output/result.png", dpi=150)
print(f"감지된 윤곽선 수: {len(contours)}")
print(f"완료! 좌표 {len(approx)}개 추출됨")
print("좌표 샘플:", approx[:5].reshape(-1, 2).tolist())