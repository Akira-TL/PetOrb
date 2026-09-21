package com.petorb.bridge

import java.net.ServerSocket
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MultipartBatchUploaderTest {
    @Test
    fun `uploader sends one multipart images field per jpeg`() {
        val server = ServerSocket(0)
        val requestBody = AtomicReference<ByteArray>()
        val handled = CountDownLatch(1)
        val serverThread = thread(start = true, isDaemon = true) {
            server.accept().use { socket ->
                val input = socket.getInputStream().buffered()
                val headers = mutableListOf<String>()
                while (true) {
                    val line = readAsciiLine(input)
                    if (line.isEmpty()) break
                    headers += line
                }
                val isChunked = headers.any {
                    it.startsWith("Transfer-Encoding:", ignoreCase = true) &&
                        it.substringAfter(':').contains("chunked", ignoreCase = true)
                }
                val body = if (isChunked) {
                    readChunkedBody(input)
                } else {
                    val contentLength = headers
                        .first { it.startsWith("Content-Length:", ignoreCase = true) }
                        .substringAfter(':')
                        .trim()
                        .toInt()
                    input.readNBytes(contentLength)
                }
                requestBody.set(body)

                val responseBody = "{\"status\":\"COMPLETED\"}".toByteArray()
                val responseHeaders = buildString {
                    append("HTTP/1.1 200 OK\r\n")
                    append("Content-Type: application/json\r\n")
                    append("Content-Length: ${responseBody.size}\r\n")
                    append("Connection: close\r\n\r\n")
                }.toByteArray(StandardCharsets.US_ASCII)
                socket.getOutputStream().use { output ->
                    output.write(responseHeaders)
                    output.write(responseBody)
                    output.flush()
                }
                handled.countDown()
            }
        }

        val directory = Files.createTempDirectory("petorb-upload-test").toFile()
        val files = (1..3).map { index ->
            directory.resolve("frame-$index.jpg").apply {
                writeBytes(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), index.toByte(), 0xFF.toByte(), 0xD9.toByte()))
            }
        }
        try {
            val uploader = MultipartBatchUploader("http://127.0.0.1:${server.localPort}")
            val result = uploader.upload(files)
            assertTrue(result.isSuccessful)
            assertEquals(200, result.statusCode)
            assertTrue(handled.await(2, TimeUnit.SECONDS))
            val body = requestBody.get().toString(Charsets.ISO_8859_1)
            assertEquals(3, Regex("name=\\\"images\\\"").findAll(body).count())
            assertEquals(3, Regex("Content-Type: image/jpeg").findAll(body).count())
        } finally {
            server.close()
            serverThread.join(1_000)
            directory.deleteRecursively()
        }
    }

    private fun readChunkedBody(input: java.io.BufferedInputStream): ByteArray {
        val output = java.io.ByteArrayOutputStream()
        while (true) {
            val sizeLine = readAsciiLine(input)
            val size = sizeLine.substringBefore(';').trim().toInt(16)
            if (size == 0) {
                while (readAsciiLine(input).isNotEmpty()) {
                    // Consume optional trailer headers.
                }
                break
            }
            output.write(input.readNBytes(size))
            readAsciiLine(input) // trailing CRLF for this chunk
        }
        return output.toByteArray()
    }

    private fun readAsciiLine(input: java.io.BufferedInputStream): String {
        val buffer = ArrayList<Byte>()
        while (true) {
            val value = input.read()
            if (value == -1) break
            if (value == '\n'.code) break
            if (value != '\r'.code) buffer += value.toByte()
        }
        return buffer.toByteArray().toString(StandardCharsets.US_ASCII)
    }
}
