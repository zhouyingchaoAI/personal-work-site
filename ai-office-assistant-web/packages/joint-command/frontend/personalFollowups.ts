import type { CrmPlaybook } from '../../../src/services/personalWorkApi'

// Storage ownership and completion permission are not task assignment.
export function personalFollowups(tasks: CrmPlaybook['followups'], username: string) {
  if (!username) return []
  return tasks.filter(task => task.owner_staff?.username
    ? task.owner_staff.username === username
    : task.owner === username)
}
