import { useQuery } from '@tanstack/react-query'

import { getAthenaConfigRecord } from '@/athena'
import { queryClient, writeCache } from '@/lib/query-client'
import type { AthenaConfigRecord } from '@/types/athena'

// One shared cache for the whole profile config record (`GET /api/config`).
// Every settings surface (MCP, model, config) reads and writes through this key
// so a save in one shows in the others, and revisiting a tab paints the cache
// instead of blanking on a fresh fetch.
//
// Distinct from session/hooks/use-athena-config.ts, which is side-effecting —
// it pushes personality/cwd/voice/… into the session stores for live chat.
export const ATHENA_CONFIG_KEY = ['athena-config-record'] as const

// staleTime 0 → serve cache instantly, background-revalidate on every mount.
export const useAthenaConfigRecord = () =>
  useQuery({ queryKey: ATHENA_CONFIG_KEY, queryFn: getAthenaConfigRecord, staleTime: 0 })

export const setAthenaConfigCache = writeCache<AthenaConfigRecord>(ATHENA_CONFIG_KEY)

export const invalidateAthenaConfig = () => queryClient.invalidateQueries({ queryKey: ATHENA_CONFIG_KEY })
