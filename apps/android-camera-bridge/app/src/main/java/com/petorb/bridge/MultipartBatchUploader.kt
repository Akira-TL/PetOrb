package com.petorb.bridge

import java.io.BufferedOutputStream
import java.io.DataOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class MultipartBatchUploader(
    private val baseUrl: String,
    private val connectTimeoutMs: Int = 5_000,
    private val readTimeoutMs: Int = 30_000,
) {
    data class UploadResult(val statusCode: Int, val body: String) {
        val isSuccessful: Boolean get() = statusCode in 200..299
    }

    fun upload(files: List<File>): UploadResult {
        require(files.isNotEmpty()) { "batch must contain at least one JPEG" }
        require(files.size <= BatchStore.MAX_BATCH_SIZE) { "batch exceeds ${BatchStore.MAX_BATCH_SIZE} JPEGs" }
        files.forEach { file -> require(file.isFile) { "missing JPEG: ${file.absolutePath}" } }

        val boundary = "PetOrb-${UUID.randomUUID()}"
        val endpoint = URL(baseUrl.trimEnd('/') + "/api/ingest")
        val connection = endpoint.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.doOutput = true
        connection.connectTimeout = connectTimeoutMs
        connection.readTimeout = readTimeoutMs
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        connection.setRequestProperty("Accept", "application/json")
        connection.setChunkedStreamingMode(64 * 1024)

        DataOutputStream(BufferedOutputStream(connection.outputStream)).use { output ->
            files.forEach { file ->
                output.writeBytes("--$boundary\r\n")
                output.writeBytes("Content-Disposition: form-data; name=\"images\"; filename=\"${file.name}\"\r\n")
                output.writeBytes("Content-Type: image/jpeg\r\n\r\n")
                file.inputStream().use { input -> input.copyTo(output) }
                output.writeBytes("\r\n")
            }
            output.writeBytes("--$boundary--\r\n")
            output.flush()
        }

        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        connection.disconnect()
        return UploadResult(status, body)
    }
}
