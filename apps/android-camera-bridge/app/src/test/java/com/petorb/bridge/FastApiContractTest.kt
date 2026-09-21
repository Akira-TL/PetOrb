package com.petorb.bridge

import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

class FastApiContractTest {
    @Test
    fun `android uploader is accepted by real petorb fastapi`() {
        val baseUrl = System.getenv("PETORB_FASTAPI_URL")
        assumeTrue("PETORB_FASTAPI_URL not configured", !baseUrl.isNullOrBlank())
        requireNotNull(baseUrl)

        createSession(baseUrl)
        val directory = Files.createTempDirectory("petorb-fastapi-contract").toFile()
        val files = (1..3).map { index ->
            File(directory, "frame-$index.jpg").apply {
                writeBytes(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), index.toByte(), 0xFF.toByte(), 0xD9.toByte()))
            }
        }
        try {
            val result = MultipartBatchUploader(baseUrl).upload(files)
            assertEquals(200, result.statusCode)
            assertTrue(result.body.contains("\"status\":\"COMPLETED\""))
            assertTrue(result.body.contains("\"evidence_frames\""))
        } finally {
            directory.deleteRecursively()
        }
    }

    private fun createSession(baseUrl: String) {
        val connection = URL(baseUrl.trimEnd('/') + "/api/sessions").openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        val payload = "{\"animal_id\":\"ANDROID-SMOKE\"}".toByteArray()
        connection.outputStream.use { it.write(payload) }
        val code = connection.responseCode
        connection.inputStream?.close()
        connection.disconnect()
        assertEquals(201, code)
    }
}
