// 承接（assignment）动作：接受/拒绝/撤销/终止/完成 的共用逻辑
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  acceptAssignment,
  declineAssignment,
  cancelAssignment,
  completeAssignment,
} from '@/api/assignment'

function reasonPrompt(title, label) {
  return ElMessageBox.prompt(`请输入${label}原因`, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /\S+/,
    inputErrorMessage: '原因不能为空',
  })
}

// reload：动作成功或冲突后都要刷新服务端状态
export function useAssignmentActions(reload) {
  async function accept(row) {
    try {
      await ElMessageBox.confirm('确定接受该定向邀请吗？', '接受邀请', {
        type: 'info', confirmButtonText: '确定', cancelButtonText: '取消',
      })
    } catch {
      return
    }
    try {
      await acceptAssignment(row.id, row.round_no)
      ElMessage.success('已接受')
    } catch (e) {
      ElMessage.error(e)
    } finally {
      reload()
    }
  }

  async function decline(row) {
    let r
    try {
      r = await reasonPrompt('拒绝邀请', '拒绝')
    } catch {
      return
    }
    try {
      await declineAssignment(row.id, row.round_no, r.value)
      ElMessage.success('已拒绝')
    } catch (e) {
      ElMessage.error(e)
    } finally {
      reload()
    }
  }

  // isClient: 客户主管=撤权，承接主体=终止
  async function cancel(row, isClient) {
    const label = isClient ? '撤权' : '终止'
    let r
    try {
      r = await reasonPrompt(`${label}承接`, label)
    } catch {
      return
    }
    try {
      await cancelAssignment(row.id, row.round_no, r.value)
      ElMessage.success(`已${label}`)
    } catch (e) {
      ElMessage.error(e)
    } finally {
      reload()
    }
  }

  async function complete(row) {
    let r
    try {
      r = await reasonPrompt('确认完成', '完成')
    } catch {
      return
    }
    try {
      await completeAssignment(row.id, row.round_no, r.value)
      ElMessage.success('已确认完成')
    } catch (e) {
      ElMessage.error(e)
    } finally {
      reload()
    }
  }

  return { accept, decline, cancel, complete }
}
