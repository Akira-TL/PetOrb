package com.petorb.bridge

enum class VideoCodec { H264, H265 }

data class CodecConfig(
    val csd0: ByteArray,
    val csd1: ByteArray? = null,
)

class AnnexBParameterSets(private val codec: VideoCodec) {
    private var vps: ByteArray? = null
    private var sps: ByteArray? = null
    private var pps: ByteArray? = null

    fun offer(data: ByteArray): Boolean {
        splitNalUnits(data).forEach { nal ->
            val payloadOffset = startCodeSize(nal)
            if (payloadOffset >= nal.size) return@forEach
            when (codec) {
                VideoCodec.H264 -> when (nal[payloadOffset].toInt() and 0x1F) {
                    7 -> sps = nal
                    8 -> pps = nal
                }
                VideoCodec.H265 -> when ((nal[payloadOffset].toInt() and 0x7E) shr 1) {
                    32 -> vps = nal
                    33 -> sps = nal
                    34 -> pps = nal
                }
            }
        }
        return config() != null
    }

    fun config(): CodecConfig? = when (codec) {
        VideoCodec.H264 -> {
            val currentSps = sps ?: return null
            val currentPps = pps ?: return null
            CodecConfig(currentSps, currentPps)
        }
        VideoCodec.H265 -> {
            val currentVps = vps ?: return null
            val currentSps = sps ?: return null
            val currentPps = pps ?: return null
            CodecConfig(currentVps + currentSps + currentPps)
        }
    }

    private fun splitNalUnits(data: ByteArray): List<ByteArray> {
        val starts = mutableListOf<Int>()
        var index = 0
        while (index + 3 < data.size) {
            if (data[index] == 0.toByte() && data[index + 1] == 0.toByte()) {
                if (data[index + 2] == 1.toByte()) {
                    starts += index
                    index += 3
                    continue
                }
                if (index + 3 < data.size && data[index + 2] == 0.toByte() && data[index + 3] == 1.toByte()) {
                    starts += index
                    index += 4
                    continue
                }
            }
            index += 1
        }
        if (starts.isEmpty()) return emptyList()
        return starts.mapIndexed { i, start ->
            val end = starts.getOrElse(i + 1) { data.size }
            data.copyOfRange(start, end)
        }
    }

    private fun startCodeSize(nal: ByteArray): Int =
        if (nal.size >= 4 && nal[2] == 1.toByte()) 3 else 4
}
