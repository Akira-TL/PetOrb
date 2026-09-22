"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

type OrientedBBox = {
  x1: number; y1: number;
  x2: number; y2: number;
  x3: number; y3: number;
  x4: number; y4: number;
};
type Detection = {
  label: string;
  display_label: string;
  confidence: number;
  bbox: OrientedBBox;
};
type EvidenceFrame = {
  id: string;
  url: string;
  image: { width: number; height: number };
  detections: Detection[];
};
type SessionFinding = {
  label: string;
  display_label: string;
  confidence: number;
  evidence_frame_id: string;
};
type SessionStatus = "READY" | "RECEIVING" | "ANALYZING" | "COMPLETED" | "FAILED";
type SamplingSession = {
  id: string;
  animal_id: string | null;
  status: SessionStatus;
  sample_quality: string | null;
  risk_level: string | null;
  overall_judgment: string | null;
  recommendation: string | null;
  findings: SessionFinding[];
  evidence_frames: EvidenceFrame[];
  error: string | null;
  created_at: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";
const ACTIVE_STATES: SessionStatus[] = ["READY", "RECEIVING", "ANALYZING"];

const STATUS_LABEL: Record<SessionStatus, string> = {
  READY: "等待采样",
  RECEIVING: "接收图像",
  ANALYZING: "分析中",
  COMPLETED: "分析完成",
  FAILED: "检测失败",
};

const RISK_META: Record<string, { label: string; className: string }> = {
  no_obvious_abnormality: {
    label: "暂未发现明显异常",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  attention_recommended: {
    label: "建议进一步关注",
    className: "bg-amber-50 text-amber-800 border-amber-200",
  },
  veterinary_review_recommended: {
    label: "建议进一步就医评估",
    className: "bg-rose-50 text-rose-800 border-rose-200",
  },
};

async function parseApiError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return payload?.detail?.message ?? payload?.detail ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export default function DetectionWorkbench() {
  const [animalId, setAnimalId] = useState("A023");
  const [session, setSession] = useState<SamplingSession | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);

  const sessionId = session?.id ?? null;
  const status: SessionStatus = session?.status ?? "READY";
  const selectedEvidence =
    session?.evidence_frames.find((frame) => frame.id === selectedEvidenceId) ??
    session?.evidence_frames[0] ??
    null;

  useEffect(() => {
    if (!sessionId || !ACTIVE_STATES.includes(status)) return;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_URL}/api/sessions/${sessionId}`, { cache: "no-store" });
        if (!response.ok) return;
        const next = (await response.json()) as SamplingSession;
        setSession(next);
      } catch {
        // Polling failure is transient; explicit actions surface their own errors.
      }
    }, 600);
    return () => window.clearInterval(timer);
  }, [sessionId, status]);

  useEffect(() => {
    return () => {
      if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
    };
  }, [localPreviewUrl]);

  const media = useMemo(() => {
    if (selectedEvidence) {
      return {
        src: `${API_URL}${selectedEvidence.url}`,
        width: selectedEvidence.image.width,
        height: selectedEvidence.image.height,
        detections: selectedEvidence.detections,
      };
    }
    if (localPreviewUrl) {
      return { src: localPreviewUrl, width: 1280, height: 720, detections: [] as Detection[] };
    }
    return null;
  }, [localPreviewUrl, selectedEvidence]);

  async function createSession() {
    setClientError(null);
    setSelectedEvidenceId(null);
    try {
      const response = await fetch(`${API_URL}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ animal_id: animalId.trim() || null }),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      const created = (await response.json()) as SamplingSession;
      if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
      setFiles([]);
      setLocalPreviewUrl(null);
      setSession(created);
    } catch (caught) {
      setClientError(caught instanceof Error ? caught.message : "无法创建检查会话");
    }
  }

  function onChooseFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []).slice(0, 10);
    if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
    setFiles(selected);
    setLocalPreviewUrl(selected[0] ? URL.createObjectURL(selected[0]) : null);
    setClientError(null);
  }

  function uploadBatch(): Promise<SamplingSession> {
    return new Promise((resolve, reject) => {
      if (!session) {
        reject(new Error("请先创建检查会话"));
        return;
      }
      const form = new FormData();
      files.forEach((file) => form.append("images", file, file.name));
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_URL}/api/ingest`);
      xhr.upload.onloadstart = () => setSession((current) => (current ? { ...current, status: "RECEIVING" } : current));
      xhr.upload.onloadend = () => setSession((current) => (current ? { ...current, status: "ANALYZING" } : current));
      xhr.onerror = () => reject(new Error("无法连接 PetOrb Server"));
      xhr.onload = () => {
        let payload: unknown;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          const errorPayload = payload as { detail?: { message?: string } };
          reject(new Error(errorPayload.detail?.message ?? `HTTP ${xhr.status}`));
          return;
        }
        resolve(payload as SamplingSession);
      };
      xhr.send(form);
    });
  }

  async function sendLocalBatch() {
    if (!session || files.length === 0) return;
    setClientError(null);
    try {
      const completed = await uploadBatch();
      setSession(completed);
      setSelectedEvidenceId(completed.evidence_frames[0]?.id ?? null);
    } catch (caught) {
      setClientError(caught instanceof Error ? caught.message : "批次上传失败");
      try {
        const response = await fetch(`${API_URL}/api/sessions/${session.id}`, { cache: "no-store" });
        if (response.ok) setSession((await response.json()) as SamplingSession);
      } catch {
        // Preserve the explicit upload error when status refresh also fails.
      }
    }
  }

  const risk = session?.risk_level ? RISK_META[session.risk_level] : null;
  const visibleError = session?.error ?? clientError;

  return (
    <main className="min-h-screen bg-[#f3f5f7] p-4 lg:p-6">
      <section className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[1640px] flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="h-9 w-9 rounded-full border-[9px] border-slate-950 bg-white" />
            <div>
              <div className="text-lg font-black tracking-tight">PetOrb</div>
              <div className="text-xs text-slate-500">GO 3S Oral Detection Workbench</div>
            </div>
          </div>

          <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
            <input
              aria-label="Animal ID"
              value={animalId}
              onChange={(event) => setAnimalId(event.target.value)}
              disabled={session !== null && ACTIVE_STATES.includes(session.status)}
              className="w-32 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm font-bold outline-none focus:border-slate-400 disabled:opacity-50"
              placeholder="Animal ID"
            />
            <button
              type="button"
              onClick={createSession}
              disabled={session !== null && ACTIVE_STATES.includes(session.status)}
              className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              开始一次检查
            </button>
            <span
              className={`rounded-full border px-3 py-1.5 text-xs font-black ${
                status === "FAILED"
                  ? "border-red-200 bg-red-50 text-red-700"
                  : status === "COMPLETED"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : status === "ANALYZING"
                      ? "border-amber-200 bg-amber-50 text-amber-700"
                      : "border-slate-200 bg-slate-50 text-slate-700"
              }`}
            >
              {STATUS_LABEL[status]}
            </span>
          </div>
        </header>

        <div className="grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1.85fr)_minmax(360px,1fr)]">
          <section className="flex min-h-[610px] flex-col border-b border-slate-200 bg-slate-950 p-4 lg:border-b-0 lg:border-r lg:p-6">
            <div
              className="relative m-auto w-full max-w-[1120px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900"
              style={{ aspectRatio: media ? `${media.width} / ${media.height}` : "16 / 9" }}
            >
              {media ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={media.src} alt="PetOrb 口腔证据画面" className="absolute inset-0 h-full w-full object-contain" />
              ) : (
                <div className="absolute inset-0 grid place-items-center text-center text-slate-500">
                  <div>
                    <div className="mb-3 text-5xl">◎</div>
                    <div className="font-bold text-slate-300">等待 GO 3S / Camera Bridge 采样</div>
                    <div className="mt-1 text-sm">创建检查会话后，图像会自动归入当前会话</div>
                  </div>
                </div>
              )}

              {media && media.detections.length > 0 && (
                <svg
                  className="pointer-events-none absolute inset-0 h-full w-full"
                  viewBox={`0 0 ${media.width} ${media.height}`}
                  preserveAspectRatio="xMidYMid meet"
                  aria-label="四点检测区域覆盖层"
                >
                  {media.detections.map((detection, index) => {
                    const corners = [
                      [detection.bbox.x1, detection.bbox.y1],
                      [detection.bbox.x2, detection.bbox.y2],
                      [detection.bbox.x3, detection.bbox.y3],
                      [detection.bbox.x4, detection.bbox.y4],
                    ] as const;
                    const polygonPoints = corners.map(([x, y]) => `${x},${y}`).join(" ");
                    const labelX = Math.min(...corners.map(([x]) => x));
                    const labelY = Math.min(...corners.map(([, y]) => y));
                    return (
                      <g key={`${detection.label}-${index}`}>
                        <polygon
                          points={polygonPoints}
                          fill="#fb7185"
                          fillOpacity="0.12"
                          stroke="#fb7185"
                          strokeWidth={Math.max(2, media.width / 320)}
                          strokeLinejoin="round"
                          vectorEffect="non-scaling-stroke"
                        />
                        <rect
                          x={labelX}
                          y={Math.max(0, labelY - 30)}
                          width="260"
                          height="30"
                          fill="#0f172a"
                          fillOpacity="0.92"
                        />
                        <text x={labelX + 8} y={Math.max(20, labelY - 9)} fill="white" fontSize="16" fontWeight="700">
                          {`${detection.display_label} ${(detection.confidence * 100).toFixed(0)}%`}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>

            {session && session.evidence_frames.length > 0 && (
              <div className="mx-auto mt-4 flex w-full max-w-[1120px] gap-3 overflow-x-auto">
                {session.evidence_frames.map((frame, index) => (
                  <button
                    type="button"
                    key={frame.id}
                    onClick={() => setSelectedEvidenceId(frame.id)}
                    className={`relative h-20 w-32 shrink-0 overflow-hidden rounded-xl border-2 ${
                      selectedEvidence?.id === frame.id ? "border-white" : "border-white/15"
                    }`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={`${API_URL}${frame.url}`} alt={`证据帧 ${index + 1}`} className="h-full w-full object-cover" />
                    <span className="absolute bottom-1 right-1 rounded bg-slate-950/80 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      {index + 1}
                    </span>
                  </button>
                ))}
              </div>
            )}

            <details className="mx-auto mt-4 w-full max-w-[1120px] rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              <summary className="cursor-pointer font-bold text-slate-200">联调备用：没有 Camera Bridge 时手动发送 JPEG 批次</summary>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <label className="cursor-pointer rounded-lg border border-white/15 px-3 py-2 font-bold text-white hover:bg-white/10">
                  选择 1–10 张 JPEG
                  <input className="hidden" type="file" accept="image/jpeg" multiple onChange={onChooseFiles} />
                </label>
                <button
                  type="button"
                  onClick={sendLocalBatch}
                  disabled={!session || session.status !== "READY" || files.length === 0}
                  className="rounded-lg bg-white px-4 py-2 font-black text-slate-950 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  发送当前批次
                </button>
                <span className="text-slate-400">{files.length > 0 ? `已选择 ${files.length} 张` : "尚未选择图片"}</span>
              </div>
            </details>
          </section>

          <aside className="flex flex-col bg-white p-6 lg:p-8">
            <div className="mb-6">
              <div className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Detection Result</div>
              <div className="mt-2 flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-black tracking-tight text-slate-950">检测结果</h1>
                  <p className="mt-2 text-sm text-slate-500">
                    {session?.animal_id ? `Animal ID · ${session.animal_id}` : "等待开始检查"}
                  </p>
                </div>
                {risk && <span className={`rounded-xl border px-3 py-2 text-xs font-black ${risk.className}`}>{risk.label}</span>}
              </div>
            </div>

            {visibleError && (
              <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                <div className="font-black">本次检查失败</div>
                <div className="mt-1 break-words">{visibleError}</div>
              </div>
            )}

            {session?.status === "COMPLETED" ? (
              <div className="space-y-5">
                <section className="grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <div className="text-xs font-bold text-slate-400">采样质量</div>
                    <div className="mt-1 text-lg font-black text-slate-900">{session.sample_quality === "usable" ? "可分析" : "—"}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <div className="text-xs font-bold text-slate-400">证据帧</div>
                    <div className="mt-1 text-lg font-black text-slate-900">{session.evidence_frames.length} 张</div>
                  </div>
                </section>

                <section>
                  <h2 className="text-sm font-black text-slate-900">AI 观察</h2>
                  <div className="mt-2 space-y-2">
                    {session.findings.length > 0 ? (
                      session.findings.map((finding) => (
                        <button
                          type="button"
                          key={finding.label}
                          onClick={() => setSelectedEvidenceId(finding.evidence_frame_id)}
                          className="flex w-full items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4 text-left hover:border-slate-400"
                        >
                          <div>
                            <div className="font-black text-slate-900">{finding.display_label}</div>
                            <div className="mt-1 font-mono text-xs text-slate-400">{finding.label}</div>
                          </div>
                          <span className="rounded-lg bg-slate-950 px-2.5 py-1 text-xs font-black text-white">
                            {(finding.confidence * 100).toFixed(0)}%
                          </span>
                        </button>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                        本次采样未发现可报告的异常目标。
                      </div>
                    )}
                  </div>
                </section>

                <section className="rounded-2xl bg-slate-50 p-5">
                  <div className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">总体判断</div>
                  <p className="mt-2 text-base font-bold leading-7 text-slate-900">{session.overall_judgment}</p>
                </section>

                <section className="rounded-2xl border border-slate-900 bg-slate-950 p-5 text-white">
                  <div className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">建议</div>
                  <p className="mt-2 text-base font-bold leading-7 text-white">{session.recommendation}</p>
                </section>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-sm leading-7 text-slate-500">
                {status === "READY" && session
                  ? "检查会话已建立。等待 Camera Bridge 上传本次 GO 3S 采样图像。"
                  : status === "RECEIVING"
                    ? "正在接收本次采样 JPEG 批次……"
                    : status === "ANALYZING"
                      ? "图像已接收，正在逐张调用检测模型并生成证据。"
                      : "点击“开始一次检查”建立 Sampling Session。"}
              </div>
            )}

            <div className="mt-auto pt-8">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-500">
                <span className="font-black text-slate-900">医疗边界：</span>
                PetOrb 提供辅助风险观察，不构成医疗诊断。系统不会提供具体药物、剂量或治疗处方。
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
