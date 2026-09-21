package com.petorb.bridge

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SamplingGateTest {
    @Test
    fun `five second gate accepts at most ten frames at two fps`() {
        val gate = SamplingGate(startMs = 1_000L, durationMs = 5_000L, intervalMs = 500L, maxFrames = 10)

        assertTrue(gate.shouldCapture(1_000L))
        assertFalse(gate.shouldCapture(1_200L))
        for (i in 1 until 10) {
            assertTrue(gate.shouldCapture(1_000L + i * 500L))
        }
        assertFalse(gate.shouldCapture(5_999L))
        assertFalse(gate.shouldCapture(6_000L))
    }
}
