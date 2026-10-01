import { useEffect, useRef, useState, type DragEvent } from 'react'
import { ImagePlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export const MAX_IMAGE_BYTES = 20 * 1024 * 1024
export const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp']

/** Client-side check with the same limits as the server (routes/reference.py): PNG/JPEG/WebP, <= 20MB. */
export function validateImageFile(file: File): string | null {
  if (!IMAGE_TYPES.includes(file.type)) return `${file.type || '알 수 없는 형식'}: PNG, JPEG, WebP 이미지만 사용할 수 있습니다`
  if (file.size > MAX_IMAGE_BYTES) return `파일이 ${MAX_IMAGE_BYTES / (1024 * 1024)}MB를 넘습니다`
  return null
}

interface Props {
  /** called only with a file that passed validation */
  onFile: (file: File) => void
  disabled?: boolean
  testId?: string
}

/** Drag & drop or click to pick one image; shows a preview of the accepted file. */
export function DropZone({ onFile, disabled, testId = 'dropzone' }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null)

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url) }, [preview])

  function accept(file: File | undefined) {
    if (!file) return
    const problem = validateImageFile(file)
    setError(problem)
    if (problem) return
    setPreview({ url: URL.createObjectURL(file), name: file.name })
    onFile(file)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    if (!disabled) accept(e.dataTransfer.files[0])
  }

  return (
    <div className="space-y-2">
      <div
        data-testid={testId}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex min-h-48 flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-6 text-center text-sm text-muted-foreground',
          dragging && 'border-primary bg-muted',
        )}
      >
        {preview ? (
          <img src={preview.url} alt={preview.name} className="max-h-40 object-contain" data-testid={`${testId}-preview`} />
        ) : (
          <ImagePlus className="size-8" />
        )}
        <p>{preview ? preview.name : '캐릭터 이미지를 끌어다 놓거나 파일을 선택하세요 (PNG · JPEG · WebP, 20MB 이하)'}</p>
        <Button type="button" variant="outline" disabled={disabled} onClick={() => inputRef.current?.click()}>
          파일 선택
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={IMAGE_TYPES.join(',')}
          className="hidden"
          data-testid={`${testId}-input`}
          disabled={disabled}
          onChange={(e) => {
            accept(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive" data-testid={`${testId}-error`}>
          {error}
        </p>
      )}
    </div>
  )
}
