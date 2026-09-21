package com.petorb.bridge

class SamplingGate(
    private val startMs: Long,
    private val durationMs: Long = 5_000L,
    private val intervalMs: Long = 500L,
    private val maxFrames: Int = BatchStore.MAX_BATCH_SIZE,
) {
    private var captured = 0
    private var nextCaptureAtMs = startMs

    fun shouldCapture(nowMs: Long): Boolean {
        if (captured >= maxFrames) return false
        if (nowMs >= startMs + durationMs) return false
        if (nowMs < nextCaptureAtMs) return false
        captured += 1
        nextCaptureAtMs = startMs + captured * intervalMs
        return true
    }

    fun isComplete(nowMs: Long): Boolean =
        captured >= maxFrames || nowMs >= startMs + durationMs

    fun capturedCount(): Int = captured
}
