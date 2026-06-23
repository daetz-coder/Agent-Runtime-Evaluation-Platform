export interface EvaluationStreamProgress {
  dimension: string
  score: number
  progress: number
  total: number
}

export interface EvaluationStreamResult {
  scores: Record<string, number>
  overall: number
  evaluation_id?: string
}

export interface EvaluationStreamHandlers {
  onProgress?: (data: EvaluationStreamProgress) => void
  onResult?: (data: EvaluationStreamResult) => void
  onError?: (data: { dimension?: string; message: string }) => void
  onDone?: () => void
}

/** Parse SSE lines from POST /evaluations/stream. */
export async function connectEvaluationStream(
  taskId: string,
  evaluationId: string | undefined,
  handlers: EvaluationStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/v1/evaluations/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId, evaluation_id: evaluationId }),
    signal,
  })

  if (!res.ok) {
    throw new Error(`Stream failed: HTTP ${res.status}`)
  }

  await consumeSseStream(res, handlers)
}

export interface BenchmarkStreamHandlers {
  onStart?: (data: { total: number; quality_order: string[] }) => void
  onProgress?: (data: { level: string; index: number; total: number; status: string }) => void
  onResult?: (data: Record<string, unknown>) => void
  onComplete?: (data: { results: unknown[]; monotonic: boolean }) => void
  onDone?: () => void
  onError?: (message: string) => void
}

/** Parse SSE lines from POST /benchmark/monotonicity/run. */
export async function connectBenchmarkStream(
  handlers: BenchmarkStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/v1/benchmark/monotonicity/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
  })

  if (!res.ok) {
    throw new Error(`Benchmark stream failed: HTTP ${res.status}`)
  }

  await consumeSseStream(
    res,
    {
      onProgress: (data) => handlers.onProgress?.(data as never),
      onResult: (data) => handlers.onResult?.(data as never),
      onError: (data) => handlers.onError?.(data.message),
      onDone: handlers.onDone,
    },
    {
      start: (data) => handlers.onStart?.(data as never),
      complete: (data) => handlers.onComplete?.(data as never),
    },
  )
}

async function consumeSseStream(
  res: Response,
  handlers: EvaluationStreamHandlers,
  extraEvents?: Record<string, (data: unknown) => void>,
): Promise<void> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        if (!raw) continue
        try {
          const data = JSON.parse(raw)
          if (extraEvents?.[currentEvent]) {
            extraEvents[currentEvent](data)
          } else if (currentEvent === 'progress') {
            handlers.onProgress?.(data)
          } else if (currentEvent === 'result') {
            handlers.onResult?.(data)
          } else if (currentEvent === 'error') {
            handlers.onError?.(data)
          } else if (currentEvent === 'done') {
            handlers.onDone?.()
          }
        } catch {
          // ignore malformed chunks
        }
      }
    }
  }
}
