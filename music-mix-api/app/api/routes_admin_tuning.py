from __future__ import annotations

from typing import Any

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import HTMLResponse
except Exception:  # pragma: no cover
    APIRouter = None
    HTTPException = Exception
    HTMLResponse = None

from app.config.tuning_profiles import (
    activate_profile,
    active_profile_name,
    list_profile_names,
    load_tuning_profile,
    reset_profile,
    save_profile,
    tuning_profile_payload,
)


ADMIN_HTML = """<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Tuning Settings</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; background: #f7f7f7; color: #111; }
      main { max-width: 1200px; margin: 0 auto; padding: 28px; }
      h1 { margin: 0 0 16px; font-size: 28px; }
      .bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 18px; }
      select, button, input { font: inherit; padding: 8px 10px; border: 1px solid #bbb; background: #fff; }
      button { cursor: pointer; border-color: #111; }
      .active { font-weight: 700; }
      section { background: #fff; border: 1px solid #ddd; margin: 14px 0; padding: 16px; }
      h2 { margin: 0 0 12px; font-size: 18px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { border-top: 1px solid #eee; padding: 8px; text-align: left; vertical-align: top; }
      th { background: #fafafa; }
      input[type="number"] { width: 96px; }
      .key { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; }
      .desc { color: #555; font-size: 12px; line-height: 1.4; }
      .status { min-height: 20px; color: #0a6; }
    </style>
  </head>
  <body>
    <main>
      <h1>Tuning Settings</h1>
      <div class="bar">
        <label>Profile <select id="profile"></select></label>
        <button id="activate">Activate</button>
        <button id="save">Save</button>
        <button id="reset">Reset</button>
        <a href="/docs">API docs</a>
        <span id="active" class="active"></span>
      </div>
      <div id="status" class="status"></div>
      <div id="sections"></div>
    </main>
    <script>
      const sections = [
        ["Speed Zone Settings", "speed_zones", "Speed gap boundaries and control-window behavior."],
        ["Music Degree Ranges", "speed_zones.preferred_degree_ranges", "Preferred segment music_speed_degree range by zone."],
        ["Hold / Control Window Settings", "speed_zones", "Hold, confirmation, trend, and target degree transform."],
        ["Fake Groove Thresholds", "fake_groove", "Blocks segments that look energetic in signal but feel weak for running."],
        ["Connector Thresholds", "connector", "Runtime connector safety thresholds."],
        ["Diversity / Anti-repeat Settings", "diversity", "Recent segment/track repeat suppression and diversity penalties."],
        ["Coverage Audit Settings", "coverage", "Minimum candidate counts by music_speed_degree bin."],
        ["Score Weights", "weights", "Stable block scoring weights and penalties."],
        ["Pace Assist v3.4 ASC Gates", "pace_assist_v3_4", "ASC thresholds for actionable step cue ranking."],
        ["Pace-Up Latency Policy", "latency_policy", "Maximum delay budgets for pace-up cue changes."]
      ];
      const descriptions = {
        tempo_feel_drop_block: ["값보다 높으면 체감 속도감이 갑자기 떨어지는 구간을 runtime에서 제외합니다.", "낮추면 더 엄격해지고, 높이면 더 많은 segment가 통과합니다.", "0.25~0.45"],
        pulse_density_drop_block: ["pulse density가 떨어지는 fake groove를 차단합니다.", "낮추면 beat 약한 구간이 더 많이 제외됩니다.", "0.25~0.45"],
        drive_cliff_block: ["drive가 끊기는 구간을 차단합니다.", "낮추면 drop처럼 보여도 힘 빠지는 구간을 더 많이 막습니다.", "0.25~0.45"],
        effective_pulse_stability_min: ["effective pulse 안정성 최소값입니다.", "높이면 cadence lock이 약한 곡을 더 엄격히 제외합니다.", "0.45~0.70"],
        recent_track_penalty: ["최근 재생 track 반복 penalty입니다.", "더 음수이면 같은 track 반복이 줄어듭니다.", "-0.30~-0.05"],
        target_degree_delta_threshold: ["이 값보다 작은 target degree 변화는 HOLD합니다.", "낮추면 더 자주 전환되고, 높이면 더 오래 유지합니다.", "0.02~0.12"],
        zone_confirmation_sec: ["speed zone 변경 확정 시간입니다.", "낮추면 반응이 빨라지고, 높이면 GPS 흔들림에 덜 반응합니다.", "0~30"],
        min_music_hold_sec: ["최소 음악 유지 시간입니다.", "낮추면 demo처럼 빠르게 전환됩니다.", "0~45"]
      };
      let current = null;
      function pathGet(obj, path) { return path.split(".").reduce((o, k) => o?.[k], obj); }
      function pathSet(obj, path, value) {
        const keys = path.split(".");
        let target = obj;
        for (const key of keys.slice(0, -1)) target = target[key];
        target[keys.at(-1)] = value;
      }
      function walkRows(obj, prefix = "") {
        return Object.entries(obj).flatMap(([key, value]) => {
          const path = prefix ? `${prefix}.${key}` : key;
          if (value && typeof value === "object" && !Array.isArray(value)) return walkRows(value, path);
          return [[path, key, value]];
        });
      }
      function render() {
        document.querySelector("#sections").innerHTML = sections.map(([title, path, desc]) => {
          const data = pathGet(current, path);
          if (!data) return "";
          const rows = walkRows(data, path).map(([fullPath, key, value]) => {
            const meta = descriptions[key] || ["튜닝 가능한 추천 설정값입니다.", "값을 바꾸면 후보 필터링 또는 ranking에 영향을 줍니다.", "profile default 기준"];
            const isArray = Array.isArray(value);
            const input = isArray
              ? `<input data-path="${fullPath}" data-kind="array" value="${value.join(",")}" />`
              : `<input type="number" step="0.01" data-path="${fullPath}" value="${value}" />`;
            return `<tr><td class="key">${fullPath}</td><td>${input}</td><td class="desc">${meta[0]}</td><td class="desc">${meta[1]}</td><td class="desc">${meta[2]}</td></tr>`;
          }).join("");
          return `<section><h2>${title}</h2><p class="desc">${desc}</p><table><thead><tr><th>metric key</th><th>current value</th><th>한국어 설명</th><th>변경 시 영향</th><th>safe range</th></tr></thead><tbody>${rows}</tbody></table></section>`;
        }).join("");
        document.querySelectorAll("input[data-path]").forEach(input => {
          input.addEventListener("change", () => {
            const raw = input.value;
            const value = input.dataset.kind === "array" ? raw.split(",").map(Number) : Number(raw);
            pathSet(current, input.dataset.path, value);
          });
        });
      }
      async function loadList() {
        const data = await fetch("/admin/tuning-profiles").then(r => r.json());
        const select = document.querySelector("#profile");
        select.innerHTML = data.profiles.map(p => `<option value="${p}">${p}</option>`).join("");
        select.value = data.active_profile;
        document.querySelector("#active").textContent = `active: ${data.active_profile}`;
        await loadProfile(select.value);
      }
      async function loadProfile(name) {
        current = await fetch(`/admin/tuning-profiles/${name}`).then(r => r.json());
        render();
      }
      async function save() {
        const name = document.querySelector("#profile").value;
        const res = await fetch(`/admin/tuning-profiles/${name}`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(current) });
        current = await res.json();
        document.querySelector("#status").textContent = `saved ${name}`;
        render();
      }
      async function activate() {
        const name = document.querySelector("#profile").value;
        const res = await fetch(`/admin/tuning-profiles/${name}/activate`, { method: "POST" });
        const data = await res.json();
        document.querySelector("#active").textContent = `active: ${data.profile_name}`;
        document.querySelector("#status").textContent = `activated ${data.profile_name}`;
      }
      async function reset() {
        const name = document.querySelector("#profile").value;
        current = await fetch(`/admin/tuning-profiles/${name}/reset`, { method: "POST" }).then(r => r.json());
        document.querySelector("#status").textContent = `reset ${name}`;
        render();
      }
      document.querySelector("#profile").addEventListener("change", e => loadProfile(e.target.value));
      document.querySelector("#save").addEventListener("click", save);
      document.querySelector("#activate").addEventListener("click", activate);
      document.querySelector("#reset").addEventListener("click", reset);
      loadList();
    </script>
  </body>
</html>"""


if APIRouter is not None:
    router = APIRouter(prefix="/admin", tags=["admin-tuning"])

    @router.get("/tuning-settings")
    def tuning_settings():
        return HTMLResponse(ADMIN_HTML)

    @router.get("/tuning-profiles")
    def tuning_profiles():
        return {"active_profile": active_profile_name(), "profiles": list_profile_names()}

    @router.get("/tuning-profiles/{profile_name}")
    def tuning_profile(profile_name: str):
        try:
            return tuning_profile_payload(load_tuning_profile(profile_name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.post("/tuning-profiles/{profile_name}")
    def update_tuning_profile(profile_name: str, payload: dict[str, Any]):
        try:
            return tuning_profile_payload(save_profile(profile_name, payload))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/tuning-profiles/{profile_name}/activate")
    def activate_tuning_profile(profile_name: str):
        try:
            return tuning_profile_payload(activate_profile(profile_name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @router.post("/tuning-profiles/{profile_name}/reset")
    def reset_tuning_profile(profile_name: str):
        try:
            return tuning_profile_payload(reset_profile(profile_name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
else:
    router = None
