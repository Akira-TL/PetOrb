package com.petorb.bridge

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
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
}
