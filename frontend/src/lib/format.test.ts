import { describe, expect, it } from 'vitest'
import { formatLapTime, formatSignedSeconds } from './format'

describe('formatLapTime', () => {
  it('formats milliseconds as m:ss.mmm', () => {
    expect(formatLapTime(88512)).toBe('1:28.512')
  })

  it('pads seconds and milliseconds', () => {
    expect(formatLapTime(65004)).toBe('1:05.004')
  })

  it('returns a placeholder for null/undefined/non-positive/non-finite values', () => {
    expect(formatLapTime(null)).toBe('-:--.---')
    expect(formatLapTime(undefined)).toBe('-:--.---')
    expect(formatLapTime(0)).toBe('-:--.---')
    expect(formatLapTime(-100)).toBe('-:--.---')
    expect(formatLapTime(Number.NaN)).toBe('-:--.---')
  })
})

describe('formatSignedSeconds', () => {
  it('prefixes a positive delta with +', () => {
    expect(formatSignedSeconds(0.42)).toBe('+0.420')
  })

  it('keeps the sign for a negative delta', () => {
    expect(formatSignedSeconds(-0.15)).toBe('-0.150')
  })

  it('respects a custom decimal count', () => {
    expect(formatSignedSeconds(1.2, 2)).toBe('+1.20')
  })

  it('returns a placeholder for null/undefined', () => {
    expect(formatSignedSeconds(null)).toBe('---')
    expect(formatSignedSeconds(undefined)).toBe('---')
  })
})
