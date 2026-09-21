package com.petorb.bridge

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class BatchStoreTest {
    @Test
    fun `sample batch is capped at ten and can be cleared`() {
        val directory = Files.createTempDirectory("petorb-batch-test").toFile()
        val store = BatchStore(directory)
        val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xD9.toByte())

        val frames = store.replaceWithSamples(jpeg, 10)
        assertEquals(10, frames.size)
        assertEquals(10, store.listFrames().size)
        assertThrows(IllegalArgumentException::class.java) { store.replaceWithSamples(jpeg, 11) }

        store.clear()
        assertEquals(0, store.listFrames().size)
        directory.deleteRecursively()
    }

    @Test
    fun `decoded jpeg frames append until batch cap`() {
        val directory = Files.createTempDirectory("petorb-decoded-batch-test").toFile()
        val store = BatchStore(directory)
        val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0x11, 0xFF.toByte(), 0xD9.toByte())

        store.clear()
        repeat(BatchStore.MAX_BATCH_SIZE) { index ->
            assertTrue(store.appendJpeg(jpeg, index.toLong()))
        }
        assertEquals(BatchStore.MAX_BATCH_SIZE, store.listFrames().size)
        assertEquals(false, store.appendJpeg(jpeg, 999L))
        directory.deleteRecursively()
    }
}
