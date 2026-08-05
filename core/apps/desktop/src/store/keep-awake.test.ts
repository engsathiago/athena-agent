import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { storedBoolean } from '@/lib/storage'

import { $keepAwake, setKeepAwake } from './keep-awake'

const KEY = 'athena.desktop.keepAwake.v1'
const desktopWindow = window as unknown as { athenaDesktop?: Window['athenaDesktop'] }
const initialAthenaDesktop = desktopWindow.athenaDesktop
const setKeepAwakeBridge = vi.fn()

beforeEach(() => {
  desktopWindow.athenaDesktop = { setKeepAwake: setKeepAwakeBridge } as unknown as Window['athenaDesktop']
  setKeepAwake(false)
  setKeepAwakeBridge.mockClear()
})

afterEach(() => {
  desktopWindow.athenaDesktop = initialAthenaDesktop
})

describe('keep-awake store', () => {
  it('persists the pref and mirrors it to the main process', () => {
    setKeepAwake(true)
    expect($keepAwake.get()).toBe(true)
    expect(storedBoolean(KEY, false)).toBe(true)
    expect(setKeepAwakeBridge).toHaveBeenLastCalledWith(true)

    setKeepAwake(false)
    expect(storedBoolean(KEY, true)).toBe(false)
    expect(setKeepAwakeBridge).toHaveBeenLastCalledWith(false)
  })
})
