import { QueryClient } from '@tanstack/react-query'

async function throwIfResNotOk(res: Response) {
  if (!res.ok) {
    throw new Error(`HTTP error! status: ${res.status}`)
  }
}

export async function apiRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const res = await fetch(`/api${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })
  
  await throwIfResNotOk(res)
  return res.json()
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: async ({ queryKey }) => {
        const [url] = queryKey as [string]
        return apiRequest(url)
      },
    },
  },
})