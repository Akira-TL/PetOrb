"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

type BBox = { x1: number; y1: number; x2: number; y2: number };
type Detection = {
  label: string;
  display_label: string;
  confidence: number;
  bbox: BBox;
};
type DetectResult = {
  status: "completed";
  image: { width: number; height: number };
  detections: Detection[];
};
type UiState = "READY" | "ANALYZING" | "COMPLETED" | "FAILED";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

function stateLabel(state: UiState): string {
  return {
    READY: "等待检测",
    ANALYZING: "分析中",
    COMPLETED: "分析完成",
    FAILED: "检测失败",
  }[state];
}

export default function DetectionWorkbench() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<DetectResult | null>(null);
  const [state, setState] = useState<UiState>("READY");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const aspectRatio = result
    ? `${result.image.width} / ${result.image.height}`
    : "16 / 9";

  const summary = useMemo(() => {
    if (!result) return "等待上传一张 GO 3S 采样图像。";
    if (result.detections.length === 0) return "本图未检测到可报告目标。";
    return `本图检测到 ${result.detections.length} 个需要关注的区域。`;
  }, [result]);

  function onChooseFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(selected);
    setPreviewUrl(selected ? URL.createObjectURL(selected) : null);
    setResult(null);
    setError(null);
    setState("READY");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setState("ANALYZING");
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append("image", file, file.name);

    try {
      const response = await fetch(`${API_URL}/api/detect`, {
        method: "POST",
        body: form,
      });
      const payload = await response.json();
      if (!response.ok) {
        const message = payload?.detail?.message ?? `HTTP ${response.status}`;
        throw new Error(message);
      }
      setResult(payload as DetectResult);
      setState("COMPLETED");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "未知错误");
      setState("FAILED");
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f6f8] p-4 lg:p-6">
      <section className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[1600px] flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="h-9 w-9 rounded-full border-[9px] border-slate-950 bg-white" />
            <div>
              <div className="text-lg font-black tracking-tight">PetOrb</div>
              <div className="text-xs text-slate-500">Oral Detection Workbench</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-600">
              单图检测闭环
            </span>
            <span
              className={`rounded-full px-3 py-1.5 text-xs font-black ${
                state === "FAILED"
                  ? "bg-red-50 text-red-700"
                  : state === "COMPLETED"
                    ? "bg-emerald-50 text-emerald-700"
                    : state === "ANALYZING"
                      ? "bg-amber-50 text-amber-700"
                      : "bg-slate-100 text-slate-700"
              }`}
            >
              {stateLabel(state)}
            </span>
          </div>
        </header>

        <div className="grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1.8fr)_minmax(340px,1fr)]">
          <section className="flex min-h-[560px] flex-col border-b border-slate-200 bg-slate-950 p-4 lg:border-b-0 lg:border-r lg:p-6">
            <div
              className="relative m-auto w-full max-w-[1100px] overflow-hidden rounded-2xl border border-white/10 bg-slate-900"
              style={{ aspectRatio }}
            >
              {previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewUrl}
                  alt="待检测口腔图像"
                  className="absolute inset-0 h-full w-full object-contain"
                />
              ) : (
                <div className="absolute inset-0 grid place-items-center text-center text-slate-500">
                  <div>
                    <div className="mb-3 text-5xl">◎</div>
                    <div className="font-bold text-slate-300">等待 GO 3S 图像</div>
                    <div className="mt-1 text-sm">当前 Ticket 使用手动 JPEG 验证真实检测链路</div>
                  </div>
                </div>
              )}

              {result && (
                <svg
                  className="pointer-events-none absolute inset-0 h-full w-full"
                  viewBox={`0 0 ${result.image.width} ${result.image.height}`}
                  preserveAspectRatio="xMidYMid meet"
                  aria-label="检测框覆盖层"
                >
                  {result.detections.map((detection, index) => {
                    const { x1, y1, x2, y2 } = detection.bbox;
                    const width = x2 - x1;
                    const height = y2 - y1;
                    return (
                      <g key={`${detection.label}-${index}`}>
                        <rect
                          x={x1}
                          y={y1}
                          width={width}
                          height={height}
                          fill="none"
                          stroke="#fb7185"
                          strokeWidth={Math.max(2, result.image.width / 320)}
                          vectorEffect="non-scaling-stroke"
                        />
                        <rect
                          x={x1}
                          y={Math.max(0, y1 - 30)}
                          width={Math.min(width, 250)}
                          height="30"
                          fill="#0f172a"
                          fillOpacity="0.92"
                        />
                        <text
                          x={x1 + 8}
                          y={Math.max(20, y1 - 9)}
                          fill="white"
                          fontSize="16"
                          fontWeight="700"
                        >
                          {`${detection.display_label} ${(detection.confidence * 100).toFixed(0)}%`}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>

            <form onSubmit={onSubmit} className="mx-auto mt-4 flex w-full max-w-[1100px] flex-wrap items-center gap-3">
              <label className="cursor-pointer rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-bold text-white hover:bg-white/10">
                选择 JPEG
                <input className="hidden" type="file" accept="image/jpeg" onChange={onChooseFile} />
              </label>
              <button
                type="submit"
                disabled={!file || state === "ANALYZING"}
                className="rounded-xl bg-white px-5 py-2.5 text-sm font-black text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {state === "ANALYZING" ? "正在调用 Detector…" : "开始检测"}
              </button>
              <span className="min-w-0 truncate text-sm text-slate-400">
                {file?.name ?? "尚未选择图片"}
              </span>
            </form>
          </section>

          <aside className="flex flex-col bg-white p-6 lg:p-8">
            <div className="mb-7">
              <div className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Detection Result</div>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">检测结果</h1>
              <p className="mt-3 text-sm leading-6 text-slate-500">{summary}</p>
            </div>

            {error && (
              <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                <div className="font-black">Detector 调用失败</div>
                <div className="mt-1 break-words">{error}</div>
              </div>
            )}

            <div className="space-y-3">
              {result?.detections.map((detection, index) => (
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
                  <div className="mt-3 text-xs text-slate-500">
                    bbox · {detection.bbox.x1}, {detection.bbox.y1} → {detection.bbox.x2}, {detection.bbox.y2}
                  </div>
                </article>
              ))}

              {result && result.detections.length === 0 && (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-800">
                  当前图片未检测到可报告目标。
                </div>
              )}

              {!result && !error && (
                <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-sm leading-6 text-slate-500">
                  上传一张 JPEG 后，这里会显示 Detector 返回的类别、置信度与检测框信息。多帧风险判断与就医建议将在下一张 Ticket 接入。
                </div>
              )}
            </div>

            <div className="mt-auto pt-8">
              <div className="rounded-2xl bg-slate-950 p-4 text-sm leading-6 text-slate-300">
                <span className="font-black text-white">医疗边界：</span>
                PetOrb 提供辅助风险观察，不构成医疗诊断。
              </div>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
