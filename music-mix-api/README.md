# Mobile Running Music API

GPS running speed를 기반으로 음악 세그먼트를 추천하고, 다음 세그먼트로 넘어갈 믹싱 플랜을 내려주는 API 서버입니다. 이 최종본은 UI/UX 없이 기존 앱 또는 기존 백엔드에서 호출하는 API 형태로 사용하는 것을 목표로 합니다.

## 역할

- 앱 또는 기존 백엔드가 GPS 구간속도와 현재 재생 상태를 보냅니다.
- API는 최근 30초 러닝 상태를 안정화해서 현재 러너가 목표 속도보다 느린지, 충분한지, 빠른지 판단합니다.
- 사전 분석된 음악 세그먼트 DB에서 BPM, phrase, section, ASC(step cue), pulse, groove, pace assist 점수를 기반으로 다음 세그먼트를 추천합니다.
- 현재 세그먼트와 다음 세그먼트 사이의 crossfade/mix plan을 제공합니다.
- 실제 오디오 재생, preload, seek, fade/crossfade 실행은 앱 또는 재생 엔진이 담당합니다.

## 실행

```bash
cd music-mix-api
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

개발 중 자동 reload:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

상태 확인:

```http
GET /health
```

응답:

```json
{"status":"ok"}
```

OpenAPI 문서:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## 데이터 준비

음악 파일을 먼저 분석해서 `data/segments`에 세그먼트 DB를 만들어야 합니다.

```bash
python scripts/ingest_edm_samples.py --source-dir D:\running\SAMPLE_V2
```

생성되는 주요 파일:

```text
data/audio/edm_samples/*.mp3
data/manifests/edm_sample_manifest.csv
data/segments/*_analysis.json
data/segments/*_segments.json
data/segments/edm_segment_db.json
```

추천에서 제외할 곡은 아래 파일에 넣습니다.

```text
data/config/blocked_tracks.json
```

현재 제외된 곡:

```json
{
  "track_ids": ["edm_010"],
  "track_titles": ["djdoblina edm short 504668"],
  "audio_file_names": ["djdoblina-edm-short-504668.mp3"]
}
```

## 연동 흐름

1. 앱이 GPS 위치를 수집합니다.
2. 앱 또는 기존 백엔드가 5-10초 단위 구간속도를 계산합니다.
3. 최근 30-60초 speed sample을 `running_samples`에 담아 `/api/v1/mobile/running-music/next-segment`를 호출합니다.
4. 응답의 `should_switch`가 `true`이면 `selected_segment`와 `playback_plan`을 사용해 다음 오디오를 preload/seek합니다.
5. 현재 세그먼트와 다음 세그먼트의 정확한 믹싱 타임라인이 필요하면 `/api/v1/mobile/mix-plans`를 호출합니다.
6. 재생 후 skip/dislike/성과 데이터가 있으면 `/api/v1/mobile/running-music/outcomes`로 보냅니다.

## GPS 구간속도 입력

서버는 GPS raw latitude/longitude를 직접 받지 않습니다. 기존 앱 또는 기존 백엔드에서 구간속도를 계산해서 보냅니다.

권장 계산:

```text
segment_speed_kmh = distance_m / elapsed_sec * 3.6
```

권장 샘플링:

- GPS point는 1초 또는 OS가 제공하는 주기로 수집합니다.
- 구간속도는 5-10초 window로 계산합니다.
- 튀는 GPS 값은 앱/백엔드에서 1차 필터링합니다.
- API에는 최근 30초 이상, 가능하면 60초 이내 sample을 보냅니다.
- `timestamp_sec`는 세션 시작 후 상대 시간 또는 서버/앱 기준 monotonic seconds면 충분합니다. 같은 요청 안에서 순서만 맞으면 됩니다.

pace 변환:

```text
pace_sec_per_km = 3600 / speed_kmh
```

예:

```text
12.0 km/h -> 300 sec/km
10.0 km/h -> 360 sec/km
7.5 km/h  -> 480 sec/km
```

## 주요 API

```http
POST /api/v1/mobile/running-music/next-segment
POST /api/v1/mobile/running-music/segment-queue
POST /api/v1/mobile/running-music/outcomes
POST /api/v1/mobile/mix-plans
GET  /api/v1/mobile/running-music/segments
GET  /debug/audio-library
GET  /debug/segment-db
GET  /debug/coverage-audit
GET  /admin/tuning-profiles
POST /admin/tuning-profiles/{profile_name}/activate
GET  /health
```

## 다음 곡 추천

```http
POST /api/v1/mobile/running-music/next-segment
Content-Type: application/json
```

요청 예시:

```json
{
  "session_id": "run-20260623-user-42",
  "user_id": "user-42",
  "running_context": {
    "current_pace_sec_per_km": 360,
    "target_pace_sec_per_km": 300,
    "current_cadence_spm": 165,
    "target_cadence_spm": 172,
    "speed_20s_ago_kmh": 9.6,
    "running_samples": [
      {"timestamp_sec": 100, "speed_kmh": 9.7, "cadence_spm": 163},
      {"timestamp_sec": 110, "speed_kmh": 9.9, "cadence_spm": 164},
      {"timestamp_sec": 120, "speed_kmh": 10.0, "cadence_spm": 165}
    ],
    "previous_target_music_speed_degree": 0.58,
    "near_phrase_boundary": true,
    "running_mode": "speed_degree_v2",
    "fatigue_level": null
  },
  "playback_context": {
    "current_track_id": "edm_028",
    "current_segment_id": "edm_028_seg_001",
    "current_position_sec": 42.0,
    "current_segment_played_sec": 42.0,
    "seconds_since_last_switch": 60.0,
    "previous_target_energy": 0.55,
    "recent_track_ids": ["edm_028", "edm_031", "edm_015"],
    "recent_segment_ids": ["edm_028_seg_001", "edm_031_seg_006", "edm_015_seg_002"],
    "force_adjust": false,
    "current_music_ASC_spm": 136.0
  },
  "client_context": {
    "platform": "ios",
    "app_version": "1.0.0",
    "network_type": "wifi",
    "battery_saver_enabled": false
  },
  "constraints": {
    "min_segment_duration_sec": 20,
    "max_segment_duration_sec": 90,
    "allow_same_track": true,
    "prefer_preloaded_audio": true,
    "energy_window": 0.35
  }
}
```

필수 필드:

- `session_id`: 러닝 세션 단위 ID입니다.
- `running_context.current_pace_sec_per_km`: 현재 구간속도를 pace로 변환한 값입니다.
- `running_context.target_pace_sec_per_km`: 사용자의 목표 속도입니다.
- `running_context.running_samples`: 최근 구간속도 샘플입니다.
- `playback_context.current_segment_id`: 현재 재생 중인 세그먼트입니다. 첫 곡이면 `null` 가능합니다.
- `playback_context.recent_track_ids`, `recent_segment_ids`: 반복 방지를 위해 최근 재생 이력을 넣습니다.

응답에서 백엔드/앱이 주로 볼 필드:

```json
{
  "should_switch": true,
  "selected_segment": {
    "segment_id": "edm_014_seg_003",
    "track_id": "edm_014",
    "audio_url": "/audio/jakob-welik-we-own-the-night-463855.mp3",
    "start_sec": 51.2,
    "end_sec": 102.8,
    "section_type": "groove",
    "bpm": 129.199,
    "phrase_confidence": 0.9,
    "metadata": {
      "track_title": "jakob welik we own the night 463855",
      "audio_file_name": "jakob-welik-we-own-the-night-463855.mp3",
      "music_speed_degree": 0.5169,
      "primary_ASC_spm": 129.199,
      "pace_assist_score": 0.654
    }
  },
  "playback_plan": {
    "start_at_sec": 51.2,
    "recommended_play_until_sec": 102.8,
    "fade_out_current_sec": 2.0,
    "fade_in_next_sec": 2.0,
    "preload_required": true,
    "transition_method": "direct_fade"
  },
  "retry_after_sec": null,
  "reason": {
    "debug_intention_label": "push",
    "target_music_speed_degree": 0.75,
    "speed_degree_debug": {
      "current_speed_kmh": 10.0,
      "target_speed_kmh": 12.0,
      "route_type": "DIRECT",
      "candidate_pool_warning": []
    }
  }
}
```

처리 규칙:

- `should_switch=true`: 앱은 `selected_segment.audio_url`을 preload하고 `playback_plan.start_at_sec`부터 재생합니다.
- `should_switch=false`: 현재 음악을 유지합니다. `retry_after_sec` 이후 다시 호출하면 됩니다.
- `force_adjust=true`: 테스트 또는 사용자가 즉시 변경을 요청한 경우에만 사용합니다. 일반 자동 추천에서는 `false` 권장입니다.

## 믹싱 플랜

추천 결과로 받은 다음 세그먼트와 현재 세그먼트 사이의 정확한 fade/crossfade 타임라인이 필요할 때 호출합니다.

```http
POST /api/v1/mobile/mix-plans
Content-Type: application/json
```

요청:

```json
{
  "current_segment_id": "edm_028_seg_001",
  "next_segment_id": "edm_014_seg_003",
  "current_position_sec": 42.0
}
```

응답:

```json
{
  "method": "phrase_aligned_equal_power_crossfade",
  "current_exit": {
    "track_id": "edm_028",
    "time_sec": 58.2
  },
  "next_entry": {
    "track_id": "edm_014",
    "time_sec": 51.2
  },
  "duration_bars": 8,
  "duration_sec": 2.0,
  "timeline": [
    {"offset_sec": 0.0, "track": "current", "action": "fade_out", "duration_sec": 2.0},
    {"offset_sec": 0.0, "track": "next", "action": "fade_in", "duration_sec": 2.0}
  ]
}
```

앱 재생 엔진 구현 포인트:

- `audio_url`은 서버의 `/audio/{file_name}` 정적 파일 경로입니다.
- 앱은 오디오를 먼저 preload합니다.
- `selected_segment.start_sec` 또는 `playback_plan.start_at_sec`로 seek합니다.
- `mix-plans.timeline`에 따라 current gain down, next gain up을 실행합니다.
- crossfade를 앱에서 구현하기 어렵다면 `playback_plan.fade_out_current_sec`와 `fade_in_next_sec`만 사용해도 됩니다.

## 세그먼트 큐

여러 후보를 미리 받고 싶을 때 사용합니다.

```http
POST /api/v1/mobile/running-music/segment-queue?queue_size=3
```

요청 body는 `next-segment`와 동일합니다.

응답:

```json
{
  "queue": [
    {
      "segment_id": "edm_014_seg_003",
      "track_id": "edm_014",
      "audio_url": "/audio/...",
      "start_sec": 51.2,
      "end_sec": 102.8
    }
  ],
  "expires_in_sec": 180
}
```

## 결과/피드백 로깅

러닝 반응 데이터가 있으면 추천 품질 개선용으로 보냅니다.

```http
POST /api/v1/mobile/running-music/outcomes
Content-Type: application/json
```

예시:

```json
{
  "segment_id": "edm_014_seg_003",
  "track_id": "edm_014",
  "session_id": "run-20260623-user-42",
  "decision_id": "dec_xxxxx",
  "speed_state": "pace_up",
  "target_speed_kmh": 12.0,
  "control_speed_before": 10.0,
  "control_speed_after_30s": 10.7,
  "control_speed_after_60s": 11.2,
  "cadence_before_spm": 165,
  "cadence_after_30s_spm": 168,
  "cadence_after_60s_spm": 170,
  "user_skip": false,
  "user_dislike": false,
  "manual_bad_segment": false,
  "manual_label": "good_pace_up"
}
```

## 디버그/운영 확인

음악 DB 로딩 상태:

```http
GET /debug/audio-library
```

세그먼트 목록:

```http
GET /debug/segment-db
```

속도 구간별 후보 커버리지:

```http
GET /debug/coverage-audit
```

튜닝 프로필 목록:

```http
GET /admin/tuning-profiles
```

튜닝 프로필 활성화:

```http
POST /admin/tuning-profiles/pace_up_responsive/activate
```

현재 기본 활성 프로필은 `pace_up_responsive`입니다. 최근 트랙 반복 패널티와 sparse-pool fallback이 적용되어 특정 4곡만 반복되는 상황을 완화합니다.

## 추천 로직 핵심 필드

- `music_speed_degree`: 음악이 느리게/빠르게 느껴지는 정도입니다. 0에 가까울수록 calm/control, 1에 가까울수록 strong push입니다.
- `primary_ASC_spm`: 러너가 발걸음 cue로 쓸 수 있는 음악 pulse입니다.
- `pace_assist_score`: 러닝 보조에 적합한 cue/groove/semantic 종합 점수입니다.
- `transition_slope`: 해당 세그먼트가 음악 속도감을 올리는지/내리는지 나타냅니다.
- `candidate_pool_warning`: 후보 풀이 좁을 때 서버가 남기는 경고입니다.
- `decision_id`: 추천 결정 로그 추적 ID입니다.

## 백엔드 연결 체크리스트

- GPS raw point를 API에 직접 보내지 말고, 앱/기존 백엔드에서 구간속도 `speed_kmh`로 변환합니다.
- `running_samples`는 최근 30초 이상 유지합니다.
- `recent_track_ids`, `recent_segment_ids`는 최소 최근 8개, 권장 최근 20개 이상 유지합니다.
- 앱이 현재 음악의 ASC를 알고 있으면 `current_music_ASC_spm`을 같이 보냅니다. 모르면 `null` 가능합니다.
- 첫 재생이면 `current_track_id`, `current_segment_id`, `current_music_ASC_spm`은 `null`로 보냅니다.
- 추천 응답의 `audio_url`은 API 서버 기준 상대 URL입니다. 앱 또는 백엔드에서 API base URL을 붙여 사용합니다.
- 운영 배포 시 API gateway 또는 기존 백엔드 앞단에서 인증, rate limit, CORS 정책을 붙입니다. 이 프로젝트 자체에는 인증 미들웨어가 아직 없습니다.
- iOS/Android가 직접 호출할 경우 HTTPS가 필요합니다.

## 파일 구조

```text
app/main.py                         FastAPI entrypoint
app/api/routes_mobile_running_music.py
app/api/routes_mobile_mix.py
app/analysis/                       음악 분석/러닝 추천 core
app/recommendation/                 추천 선택/로그/피드백
app/mix/                            믹싱 플랜
data/audio/edm_samples/             분석된 mp3 파일
data/segments/                      분석 결과와 세그먼트 DB
data/config/blocked_tracks.json     추천 제외곡 목록
data/config/pace_tuning_profiles/   추천 튜닝 프로필
scripts/ingest_edm_samples.py       mp3 ingest + analysis
```

## 테스트

```bash
python -m pytest
```

현재 최종본 기준 전체 테스트는 73개입니다.
