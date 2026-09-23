const STORAGE_KEY = 'petorb:peak-scores:v1'
const TYPES = ['ulcer', 'tartar']
let memoryPeaks = { ulcer: 0, tartar: 0 }

function validConfidence(value) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.min(1, Math.max(0, number)) : 0
}

export function mergePeakScores(previous, incoming) {
  return Object.fromEntries(TYPES.map(type => [
    type,
    Math.max(
      validConfidence(previous?.[type]),
      incoming?.[type]?.found ? validConfidence(incoming[type].conf) : 0,
    ),
  ]))
}

export function readPeakScores() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}')
    memoryPeaks = mergePeakScores(memoryPeaks, {
      ulcer: { found: true, conf: saved.ulcer },
      tartar: { found: true, conf: saved.tartar },
    })
  } catch {
    // The in-memory values still work if browser storage is unavailable.
  }
  return memoryPeaks
}

function scoreObjects(peaks, current = {}) {
  return Object.fromEntries(TYPES.map(type => [type, {
    ...current[type],
    conf: peaks[type],
    found: peaks[type] > 0,
  }]))
}

export function keepPeakScores(user, replays = []) {
  const replayPeaks = replays.reduce((peaks, replay) => mergePeakScores(peaks, {
    ulcer: { found: Number(replay.ulcer) > 0, conf: replay.ulcer },
    tartar: { found: Number(replay.tartar) > 0, conf: replay.tartar },
  }), readPeakScores())
  memoryPeaks = mergePeakScores(replayPeaks, user.scores)
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memoryPeaks))
  } catch {
    // The current page still retains the peaks in memory.
  }
  return { ...user, scores: scoreObjects(memoryPeaks, user.scores) }
}

export function restoredPeakUser() {
  const peaks = readPeakScores()
  if (!TYPES.some(type => peaks[type] > 0)) return null
  return { frames: 0, scores: scoreObjects(peaks) }
}
