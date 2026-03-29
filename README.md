# ArtRun Backend

AI 기반 GPS 아트 러닝 코스 생성 서비스 백엔드

> **현재 상태**: Gemini AI 도형 생성은 **stub 모드**로 동작합니다. API Key를 설정하면 실제 AI 생성으로 전환됩니다.

## 기술 스택

- **Java 25** / Spring Boot 4.0.5
- **PostgreSQL 16** + PostGIS 3.5 + pgRouting 4.0
- **Redis 7**
- **Gemini API** (Google AI Studio)
- Docker Compose

## 빠른 시작

### 1. 사전 요구사항

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치
- [Java 25 JDK](https://jdk.java.net/25/) 설치

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에서 필요시 수정:
- `GEMINI_API_KEY` - [Google AI Studio](https://aistudio.google.com/apikey)에서 발급 (없으면 stub 모드)
- `DB_PORT` - 로컬에 PostgreSQL이 이미 있으면 `5433` 유지, 없으면 `5432`로 변경 가능

### 3. 인프라 실행

```bash
docker compose up -d db redis
```

DB healthy 확인:
```bash
docker compose ps
```

### 4. OSM 도로 데이터 임포트 (최초 1회)

한국 전체 도로망 데이터를 DB에 임포트합니다. (약 10~15분 소요)

```bash
# 이미지 빌드
docker build -f docker/Dockerfile.osm-importer -t artrun-osm-importer docker/

# 임포트 실행
docker run --rm --network artrun-be_default \
  -e DB_HOST=artrun-db -e DB_PORT=5432 \
  -e DB_NAME=artrun -e DB_USER=artrun -e DB_PASSWORD=artrun \
  artrun-osm-importer

# 성능 인덱스 생성
docker exec artrun-db psql -U artrun -d artrun -c "
CREATE INDEX IF NOT EXISTS idx_ways_source ON ways (source);
CREATE INDEX IF NOT EXISTS idx_ways_target ON ways (target);
CREATE INDEX IF NOT EXISTS idx_ways_source_target ON ways (source, target);
CREATE INDEX IF NOT EXISTS idx_ways_tag_id ON ways (tag_id);
ANALYZE ways;
ANALYZE ways_vertices_pgr;
"
```

### 5. 앱 실행

```bash
./gradlew bootRun --args='--spring.profiles.active=local'
```

### 6. 확인

- Swagger UI: http://localhost:8080/swagger-ui/index.html
- Health Check: http://localhost:8080/actuator/health

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/routes/generate` | 경로 생성 요청 (비동기) |
| GET | `/api/v1/routes/status/{taskId}` | 경로 생성 상태 조회 |
| POST | `/api/v1/session/start` | 러닝 세션 시작 |
| POST | `/api/v1/session/{sessionId}/track` | 실시간 위치 검증 |
| POST | `/api/v1/records/save` | 러닝 결과 저장 |

### 경로 생성 예시

```bash
curl -X POST http://localhost:8080/api/v1/routes/generate \
  -H "Content-Type: application/json" \
  -d '{
    "requestText": "별 모양으로 3km 뛰고 싶어",
    "shapeType": "star",
    "activityType": "running",
    "targetDistanceKm": 3.0,
    "startPoint": {"lat": 37.5665, "lng": 126.9780},
    "preferences": {"avoidMainRoad": true, "preferPark": true}
  }'
```

## 경로 생성 파이프라인

```
사용자 입력 → AI 도형 좌표 생성 → 스케일링 → 보간점 삽입
→ OSM 도로 노드 스냅 → A*/Dijkstra 경로 연결 → 유사도/점수 산정
→ 후보 3개 반환 (점수순 정렬)
```

## 프로젝트 구조

```
src/main/java/com/artrun/server/
├── controller/     # REST API 컨트롤러
├── service/        # 비즈니스 로직 (파이프라인 5단계)
├── domain/         # JPA 엔티티
├── dto/            # 요청/응답 DTO
├── repository/     # 데이터 접근 계층
├── config/         # Spring 설정 (Security, Redis, WebSocket, Swagger)
└── common/         # 예외 처리, 공통 응답
```

## 팀

| 역할 | 담당 |
|------|------|
| Gemini AI 좌표 생성 | 수현 |
| Mapbox 연동 / 백엔드 | 유겸 |
| React Native 프론트 | 주형 |
