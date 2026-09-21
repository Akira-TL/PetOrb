package com.petorb.bridge

import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.media.Image
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.SystemClock
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer

class PreviewJpegDecoder(
    private val videoCodec: VideoCodec,
    private val width: Int,
    private val height: Int,
    private val batchStore: BatchStore,
    private val samplingGate: SamplingGate,
    private val onFrameSaved: (Int) -> Unit,
    private val onError: (Throwable) -> Unit,
) {
    private val parameterSets = AnnexBParameterSets(videoCodec)
    private var decoder: MediaCodec? = null
    private val bufferInfo = MediaCodec.BufferInfo()

    @Synchronized
    fun offer(encoded: ByteArray, timestampMs: Long) {
        try {
            val codec = decoder ?: run {
                parameterSets.offer(encoded)
                val config = parameterSets.config() ?: return
                createDecoder(config).also { decoder = it }
            }
            val inputIndex = codec.dequeueInputBuffer(0)
            if (inputIndex >= 0) {
                val input = codec.getInputBuffer(inputIndex) ?: return
                if (encoded.size > input.capacity()) {
                    throw IllegalArgumentException("preview access unit exceeds MediaCodec input buffer")
                }
                input.clear()
                input.put(encoded)
                codec.queueInputBuffer(inputIndex, 0, encoded.size, timestampMs * 1_000L, 0)
            }
            drain(codec)
        } catch (error: Throwable) {
            onError(error)
        }
    }

    @Synchronized
    fun release() {
        val codec = decoder ?: return
        decoder = null
        runCatching { codec.stop() }
        codec.release()
    }

    private fun createDecoder(config: CodecConfig): MediaCodec {
        val mime = if (videoCodec == VideoCodec.H265) MediaFormat.MIMETYPE_VIDEO_HEVC else MediaFormat.MIMETYPE_VIDEO_AVC
        val format = MediaFormat.createVideoFormat(mime, width, height).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            setByteBuffer("csd-0", ByteBuffer.wrap(config.csd0))
            config.csd1?.let { setByteBuffer("csd-1", ByteBuffer.wrap(it)) }
        }
        return MediaCodec.createDecoderByType(mime).apply {
            configure(format, null, null, 0)
            start()
        }
    }

    private fun drain(codec: MediaCodec) {
        while (true) {
            val outputIndex = codec.dequeueOutputBuffer(bufferInfo, 0)
            when {
                outputIndex >= 0 -> {
                    val now = SystemClock.elapsedRealtime()
                    val image = runCatching { codec.getOutputImage(outputIndex) }.getOrNull()
                    if (image != null && bufferInfo.size > 0 && samplingGate.shouldCapture(now)) {
                        image.use {
                            val jpeg = imageToJpeg(it)
                            if (batchStore.appendJpeg(jpeg, bufferInfo.presentationTimeUs / 1_000L)) {
                                onFrameSaved(batchStore.listFrames().size)
                            }
                        }
                    } else {
                        image?.close()
                    }
                    codec.releaseOutputBuffer(outputIndex, false)
                }
                outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> Unit
                else -> return
            }
        }
    }

    private fun imageToJpeg(image: Image): ByteArray {
        require(image.format == ImageFormat.YUV_420_888) {
            "unsupported decoder output image format ${image.format}"
        }
        val crop = image.cropRect
        val width = crop.width()
        val height = crop.height()
        val nv21 = ByteArray(width * height * 3 / 2)
        copyPlane(image.planes[0], crop.left, crop.top, width, height, nv21, 0, 1)

        var uvOffset = width * height
        val chromaWidth = width / 2
        val chromaHeight = height / 2
        val u = image.planes[1]
        val v = image.planes[2]
        val uBuffer = u.buffer.duplicate()
        val vBuffer = v.buffer.duplicate()
        val chromaLeft = crop.left / 2
        val chromaTop = crop.top / 2
        for (row in 0 until chromaHeight) {
            for (col in 0 until chromaWidth) {
                val vIndex = (chromaTop + row) * v.rowStride + (chromaLeft + col) * v.pixelStride
                val uIndex = (chromaTop + row) * u.rowStride + (chromaLeft + col) * u.pixelStride
                nv21[uvOffset++] = vBuffer.get(vIndex)
                nv21[uvOffset++] = uBuffer.get(uIndex)
            }
        }

        val output = ByteArrayOutputStream()
        check(YuvImage(nv21, ImageFormat.NV21, width, height, null).compressToJpeg(Rect(0, 0, width, height), 88, output)) {
            "failed to encode decoded preview frame as JPEG"
        }
        return output.toByteArray()
    }

    private fun copyPlane(
        plane: Image.Plane,
        cropLeft: Int,
        cropTop: Int,
        width: Int,
        height: Int,
        output: ByteArray,
        outputOffset: Int,
        outputPixelStride: Int,
    ) {
        val buffer = plane.buffer.duplicate()
        var target = outputOffset
        for (row in 0 until height) {
            val rowStart = (cropTop + row) * plane.rowStride + cropLeft * plane.pixelStride
            for (col in 0 until width) {
                output[target] = buffer.get(rowStart + col * plane.pixelStride)
                target += outputPixelStride
            }
        }
    }
}
