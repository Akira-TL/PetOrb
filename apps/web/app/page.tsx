"use client";

import { useEffect, useRef, useState } from "react";

type OrientedBBox = {
  x1: number; y1: number;
  x2: number; y2: number;
  x3: number; y3: number;
  x4: number; y4: number;
};

type Detection = {
  label: "gingi" | "sarro";
  display_label: string;
  confidence: number;
  bbox: OrientedBBox;
};

type InferenceMessage = {
  type: "inference";
  frame_id: number;
  risk_level: string;
  overall_judgment: string;
  recommendation: string;
  detections: Detection[];
};

type StreamStatusMessage = {
  type: "stream_status";
  status: string;
  camera_connected?: boolean;
  frame_id?: number;
  codec?: string | null;
  width?: number | null;
  height?: number | null;
  source_fps?: number | null;
  display_fps?: number;
  inference_fps?: number;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";
const VIEW_WS_URL = `${API_URL.replace(/^http/, "ws")}/ws/camera/view`;

const RISK_META: Record<string, { label: string; className: string }> = {
  no_obvious_abnormality: {
    label: "暂未发现明显异常",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  attention_recommended: {
    label: "建议进一步关注",
    className: "border-amber-200 bg-amber-50 text-amber-800",
  },
  veterinary_review_recommended: {
    label: "建议进一步就医评估",
    className: "border-rose-200 bg-rose-50 text-rose-800",
  },
};

function drawDetections(ctx: CanvasRenderingContext2D, detections: Detection[]) {
  for (const detection of detections) {
    const corners = [
      [detection.bbox.x1, detection.bbox.y1],
      [detection.bbox.x2, detection.bbox.y2],
      [detection.bbox.x3, detection.bbox.y3],
      [detection.bbox.x4, detection.bbox.y4],
    ] as const;
    const labelX = Math.min(...corners.map(([x]) => x));
    const labelY = Math.min(...corners.map(([, y]) => y));

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(corners[0][0], corners[0][1]);
    corners.slice(1).forEach(([x, y]) => ctx.lineTo(x, y));
    ctx.closePath();
    ctx.fillStyle = "rgba(251, 113, 133, 0.14)";
    ctx.strokeStyle = "rgb(251, 113, 133)";
    ctx.lineWidth = Math.max(2, ctx.canvas.width / 320);
    ctx.lineJoin = "round";
    ctx.fill();
    ctx.stroke();

    const label = `${detection.display_label} ${(detection.confidence * 100).toFixed(0)}%`;
    ctx.font = `700 ${Math.max(14, ctx.canvas.width / 70)}px system-ui`;
    const metrics = ctx.measureText(label);
    const padding = 8;
    const boxHeight = Math.max(26, ctx.canvas.height / 24);
    const boxY = Math.max(0, labelY - boxHeight);
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.fillRect(labelX, boxY, metrics.width + padding * 2, boxHeight);
    ctx.fillStyle = "white";
    ctx.textBaseline = "middle";
    ctx.fillText(label, labelX + padding, boxY + boxHeight / 2);
    ctx.restore();
  }
}

export default function RealtimeDetectionWorkbench() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const detectionsRef = useRef<Detection[]>([]);
  const lastDrawnFrameRef = useRef(0);
  const [streamStatus, setStreamStatus] = useState("连接电脑服务中…");
  const [streamMeta, setStreamMeta] = useState<StreamStatusMessage | null>(null);
  const [inference, setInference] = useState<InferenceMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [videoFps, setVideoFps] = useState(0);
  const [aiFps, setAiFps] = useState(0);
  const [hasFrame, setHasFrame] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(VIEW_WS_URL);
    ws.binaryType = "arraybuffer";
    let videoFrames = 0;
    let aiResults = 0;
    let closed = false;

    const rateTimer = window.setInterval(() => {
      setVideoFps(videoFrames);
      setAiFps(aiResults);
      videoFrames = 0;
      aiResults = 0;
    }, 1000);

    ws.onopen = () => {
      setStreamStatus("等待 Camera Bridge / GO 3S");
      setError(null);
    };

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
        const payload = JSON.parse(event.data) as StreamStatusMessage | InferenceMessage | { type: string; message?: string };
        if (payload.type === "stream_status") {
          const status = payload as StreamStatusMessage;
          setStreamMeta(status);
          setStreamStatus(
            status.status === "streaming"
              ? `实时流 ${status.codec?.toUpperCase() ?? ""} · ${status.width ?? "?"}×${status.height ?? "?"} · ${status.source_fps ?? "?"} FPS`
              : status.status === "waiting_config"
                ? "Camera Bridge 已连接，等待 GO 3S 流参数"
                : "等待 Camera Bridge / GO 3S",
          );
          return;
        }
        if (payload.type === "inference") {
          const next = payload as InferenceMessage;
          detectionsRef.current = next.detections;
          setInference(next);
          setError(null);
          aiResults += 1;
          return;
        }
        if (payload.type === "inference_error" || payload.type === "stream_error") {
          setError(payload.message ?? "实时链路错误");
          return;
        }
        return;
      }

      const packet = event.data as ArrayBuffer;
      if (packet.byteLength <= 4) return;
      const frameId = new DataView(packet, 0, 4).getUint32(0, false);
      const blob = new Blob([packet.slice(4)], { type: "image/jpeg" });
      const bitmap = await createImageBitmap(blob);
      if (closed || frameId < lastDrawnFrameRef.current) {
        bitmap.close();
        return;
      }
      lastDrawnFrameRef.current = frameId;
      setHasFrame(true);
      const canvas = canvasRef.current;
      if (!canvas) {
        bitmap.close();
        return;
      }
      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        bitmap.close();
        return;
      }
      ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      drawDetections(ctx, detectionsRef.current);
      bitmap.close();
      videoFrames += 1;
    };

    ws.onerror = () => setError("无法连接 PetOrb 实时 WebSocket");
    ws.onclose = () => setStreamStatus("PetOrb 实时 WebSocket 已断开");

    return () => {
      closed = true;
      window.clearInterval(rateTimer);
      ws.close();
    };
  }, []);

  const risk = inference?.risk_level ? RISK_META[inference.risk_level] : null;
  const aspectRatio = streamMeta?.width && streamMeta?.height ? `${streamMeta.width} / ${streamMeta.height}` : "16 / 9";

  return (
    <main className="min-h-screen bg-[#f3f5f7] p-4 lg:p-6">
      <section className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[1640px] flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="h-9 w-9 rounded-full border-[9px] border-slate-950 bg-white" />
            <div>
              <div className="text-lg font-black tracking-tight">PetOrb</div>
              <div className="text-xs text-slate-500">GO 3S Realtime Oral Detection</div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-black">
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700">VIDEO {videoFps} FPS</span>
            <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-slate-700">AI {aiFps} FPS</span>
            <span className="rounded-full border border-slate-200 bg-slate-950 px-3 py-1.5 text-white">目标 30 / 10 FPS</span>
          </div>
        </header>

        <div className="grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1.85fr)_minmax(360px,1fr)]">
          <section className="flex min-h-[610px] flex-col border-b border-slate-200 bg-slate-950 p-4 lg:border-b-0 lg:border-r lg:p-6">
            <div className="mb-4 flex items-center justify-between gap-3 text-sm text-slate-300">
              <div className="font-bold">{streamStatus}</div>
              <div className="font-mono text-xs text-slate-500">{VIEW_WS_URL}</div>
            </div>
            <div
              className="relative m-auto grid w-full max-w-[1120px] place-items-center overflow-hidden rounded-2xl border border-white/10 bg-slate-900"
              style={{ aspectRatio }}
            >
              <canvas ref={canvasRef} className="h-full w-full object-contain" />
              {!hasFrame && (
                <div className="pointer-events-none absolute inset-0 grid place-items-center text-center text-slate-500">
                  <div>
                    <div className="mb-3 text-5xl">◎</div>
                    <div className="font-bold text-slate-300">等待 GO 3S 实时画面</div>
                    <div className="mt-1 text-sm">Android Bridge 通过 USB/ADB reverse 推送 H.264/H.265</div>
                  </div>
                </div>
              )}
            </div>
            {error && (
              <div className="mx-auto mt-4 w-full max-w-[1120px] rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            )}
          </section>

          <aside className="flex flex-col bg-white p-6 lg:p-8">
            <div className="mb-6">
              <div className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Realtime Detection</div>
              <div className="mt-2 flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-3xl font-black tracking-tight text-slate-950">实时检测</h1>
                  <p className="mt-2 text-sm text-slate-500">
                    {inference ? `最新 AI 帧 #${inference.frame_id}` : "等待本地 Detector 返回结果"}
                  </p>
                </div>
                {risk && <span className={`rounded-xl border px-3 py-2 text-xs font-black ${risk.className}`}>{risk.label}</span>}
              </div>
            </div>

            <section className="space-y-2">
              <h2 className="text-sm font-black text-slate-900">AI 观察</h2>
              {inference?.detections.length ? (
                inference.detections.map((detection, index) => (
                  <article key={`${detection.label}-${index}`} className="rounded-2xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-black text-slate-900">{detection.display_label}</div>
                        <div className="mt-1 font-mono text-xs text-slate-400">{detection.label}</div>
                      </div>
                      <span className="rounded-lg bg-slate-950 px-2.5 py-1 text-xs font-black text-white">
                        {(detection.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 p-5 text-sm leading-6 text-slate-500">
                  {inference ? "当前 AI 帧未检测到 gingi / sarro。" : "GO 3S 画面进入电脑后，每 3 帧抽 1 帧送本机 AI。"}
                </div>
              )}
            </section>

            <section className="mt-5 rounded-2xl bg-slate-50 p-5">
              <div className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">总体判断</div>
              <p className="mt-2 text-base font-bold leading-7 text-slate-900">
                {inference?.overall_judgment ?? "等待实时检测结果。"}
              </p>
            </section>

            <section className="mt-4 rounded-2xl border border-slate-900 bg-slate-950 p-5 text-white">
              <div className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">建议</div>
              <p className="mt-2 text-base font-bold leading-7 text-white">
                {inference?.recommendation ?? "实时结果出现后，这里显示是否建议进一步人工检查或就医评估。"}
              </p>
            </section>

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
