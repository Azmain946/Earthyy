import { useQuery } from '@tanstack/react-query'
import { jobService } from '../services'

/** Poll a processing job until it reaches a terminal state. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobService.get(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'completed' || status === 'failed' ? false : 1500
    },
  })
}
