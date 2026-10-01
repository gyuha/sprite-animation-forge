import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { PaletteEditor } from './PaletteEditor'

function Harness({ initial }: { initial: string[] }) {
  const [colors, setColors] = useState(initial)
  return <PaletteEditor label="주 색상" testId="pal" colors={colors} onChange={setColors} />
}

describe('PaletteEditor', () => {
  it('flags an invalid hex value and clears the flag once it is #RRGGBB', async () => {
    render(<Harness initial={['#C8281E']} />)
    const field = screen.getByTestId('pal-input-0')
    expect(field).toHaveAttribute('aria-invalid', 'false')

    await userEvent.clear(field)
    await userEvent.type(field, '#C8281')
    expect(field).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('#RRGGBB')

    await userEvent.type(field, 'E')
    expect(field).toHaveAttribute('aria-invalid', 'false')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('adds and removes colours', async () => {
    render(<Harness initial={['#C8281E']} />)
    await userEvent.click(screen.getByTestId('pal-add'))
    expect(screen.getByTestId('pal-input-1')).toHaveValue('#000000')
    await userEvent.click(screen.getByTestId('pal-remove-0'))
    expect(screen.queryByTestId('pal-input-1')).not.toBeInTheDocument()
    expect(screen.getByTestId('pal-input-0')).toHaveValue('#000000')
  })
})
