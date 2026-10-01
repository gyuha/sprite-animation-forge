import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DropZone, MAX_IMAGE_BYTES } from './DropZone'

const input = () => screen.getByTestId('dropzone-input')
const pick = (file: File) => fireEvent.change(input(), { target: { files: [file] } })

describe('DropZone', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn()
  })

  it('rejects a non-image type with a message and no callback', () => {
    const onFile = vi.fn()
    render(<DropZone onFile={onFile} />)
    pick(new File(['x'], 'doc.gif', { type: 'image/gif' }))
    expect(screen.getByTestId('dropzone-error')).toHaveTextContent('PNG, JPEG, WebP')
    expect(onFile).not.toHaveBeenCalled()
  })

  it('rejects a file over 20MB', () => {
    const onFile = vi.fn()
    render(<DropZone onFile={onFile} />)
    const big = new File(['x'], 'big.png', { type: 'image/png' })
    Object.defineProperty(big, 'size', { value: MAX_IMAGE_BYTES + 1 })
    pick(big)
    expect(screen.getByTestId('dropzone-error')).toHaveTextContent('20MB')
    expect(onFile).not.toHaveBeenCalled()
  })

  it('accepts a PNG, shows a preview and reports the file', () => {
    const onFile = vi.fn()
    render(<DropZone onFile={onFile} />)
    const png = new File(['x'], 'hero.png', { type: 'image/png' })
    pick(png)
    expect(onFile).toHaveBeenCalledWith(png)
    expect(screen.getByTestId('dropzone-preview')).toHaveAttribute('src', 'blob:preview')
    expect(screen.queryByTestId('dropzone-error')).not.toBeInTheDocument()
  })

  it('accepts a dropped file too', () => {
    const onFile = vi.fn()
    render(<DropZone onFile={onFile} />)
    const webp = new File(['x'], 'a.webp', { type: 'image/webp' })
    fireEvent.drop(screen.getByTestId('dropzone'), { dataTransfer: { files: [webp] } })
    expect(onFile).toHaveBeenCalledWith(webp)
  })
})
