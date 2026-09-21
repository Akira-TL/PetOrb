package com.petorb.bridge

import java.io.File

class BatchStore(private val directory: File) {
    init {
        directory.mkdirs()
    }

    fun replaceWithSamples(sampleJpeg: ByteArray, count: Int): List<File> {
        require(count in 1..MAX_BATCH_SIZE) { "sample count must be between 1 and $MAX_BATCH_SIZE" }
        clear()
        return (1..count).map { index ->
            File(directory, "frame-${index.toString().padStart(2, '0')}.jpg").apply {
                writeBytes(sampleJpeg)
            }
        }
    }

    fun listFrames(): List<File> =
        directory.listFiles { file -> file.isFile && file.extension.equals("jpg", ignoreCase = true) }
            ?.sortedBy { it.name }
            .orEmpty()

    fun clear() {
        listFrames().forEach { it.delete() }
    }

    companion object {
        const val MAX_BATCH_SIZE = 10
    }
}
