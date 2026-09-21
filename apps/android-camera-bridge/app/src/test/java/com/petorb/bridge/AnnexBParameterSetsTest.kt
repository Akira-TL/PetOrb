package com.petorb.bridge

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AnnexBParameterSetsTest {
    @Test
    fun `h264 collects sps and pps with start codes`() {
        val collector = AnnexBParameterSets(VideoCodec.H264)
        val sps = byteArrayOf(0, 0, 0, 1, 0x67, 0x64, 0x00, 0x1f)
        val pps = byteArrayOf(0, 0, 1, 0x68, 0x01, 0x02)

        assertFalse(collector.offer(sps))
        assertTrue(collector.offer(pps))
        val config = requireNotNull(collector.config())
        assertArrayEquals(sps, config.csd0)
        assertArrayEquals(pps, config.csd1)
    }

    @Test
    fun `h265 collects vps sps pps into csd0`() {
        val collector = AnnexBParameterSets(VideoCodec.H265)
        val vps = byteArrayOf(0, 0, 0, 1, (32 shl 1).toByte(), 1)
        val sps = byteArrayOf(0, 0, 0, 1, (33 shl 1).toByte(), 1)
        val pps = byteArrayOf(0, 0, 0, 1, (34 shl 1).toByte(), 1)

        collector.offer(vps)
        collector.offer(sps)
        assertTrue(collector.offer(pps))
        val config = requireNotNull(collector.config())
        assertArrayEquals(vps + sps + pps, config.csd0)
        assertTrue(config.csd1 == null)
    }
}
