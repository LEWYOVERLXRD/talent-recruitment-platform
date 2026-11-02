<template>
  <div class="app-page">
    <div class="page-head">
      <div><h1>我的简历</h1><p class="page-sub">维护个人资料并管理投递时使用的简历版本。</p></div>
      <el-upload :show-file-list="false" accept=".pdf,.docx,.txt" :before-upload="beforeUpload" :http-request="upload">
        <el-button type="primary" :loading="uploading">上传简历</el-button>
      </el-upload>
    </div>
    <el-card shadow="never" v-loading="loading">
      <template #header><div class="card-head"><strong>个人资料</strong><el-button link type="primary" @click="saveProfile">保存资料</el-button></div></template>
      <el-form :model="form" label-width="100px" class="profile-form">
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="当前公司"><el-input v-model="form.current_company" /></el-form-item>
        <el-form-item label="当前职位"><el-input v-model="form.current_position" /></el-form-item>
        <el-form-item label="最高学历"><el-input v-model="form.education" /></el-form-item>
        <el-form-item label="工作年限"><el-input-number v-model="form.years_of_experience" :min="0" /></el-form-item>
        <el-form-item label="期望薪资"><el-input v-model="form.expected_salary" /></el-form-item>
        <el-form-item label="期望地点"><el-input v-model="form.expected_location" /></el-form-item>
      </el-form>
    </el-card>
    <el-card shadow="never" class="mt" v-loading="loading">
      <template #header><strong>简历版本</strong></template>
      <el-table :data="resumes" border stripe>
        <el-table-column label="版本" width="90"><template #default="{ row }">v{{ row.version }} <el-tag v-if="row.is_primary" type="success" size="small">主简历</el-tag></template></el-table-column>
        <el-table-column prop="original_name" label="文件名" min-width="220" />
        <el-table-column label="解析状态" width="120"><template #default="{ row }">{{ parseText(row.parse_status) }}</template></el-table-column>
        <el-table-column prop="created_at" label="上传时间" min-width="170" />
        <el-table-column label="操作" width="120"><template #default="{ row }"><el-button v-if="!row.is_primary" link type="primary" @click="setPrimary(row)">设为主简历</el-button></template></el-table-column>
      </el-table>
      <el-empty v-if="!loading && !resumes.length" description="暂无简历，请先上传一份简历" />
    </el-card>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getProfile, updateProfile, listMyResumes, uploadMyResume, setMyPrimaryResume } from '@/api/jobseeker'
const loading = ref(false); const uploading = ref(false); const resumes = ref([]); const profile = ref(null)
const form = reactive({ name: '', phone: '', email: '', current_company: '', current_position: '', education: '', years_of_experience: null, expected_salary: '', expected_location: '' })
function fill(data) { profile.value = data; Object.assign(form, data) }
function parseText(s) { return { pending: '待解析', success: '已解析', failed: '解析失败' }[s] || s || '-' }
function beforeUpload(file) { if (!/\.(pdf|docx|txt)$/i.test(file.name)) { ElMessage.warning('仅支持 PDF、DOCX、TXT'); return false }; if (file.size > 10 * 1024 * 1024) { ElMessage.warning('文件不能超过 10 MiB'); return false }; return true }
async function load() { loading.value = true; try { fill(await getProfile()); resumes.value = (await listMyResumes()).items || [] } catch (e) { ElMessage.error(e.message || e) } finally { loading.value = false } }
async function saveProfile() { try { fill(await updateProfile({ name: form.name, phone: form.phone || null, email: form.email || null, current_company: form.current_company || null, current_position: form.current_position || null, education: form.education || null, years_of_experience: form.years_of_experience, expected_salary: form.expected_salary || null, expected_location: form.expected_location || null })); ElMessage.success('个人资料已保存') } catch (e) { ElMessage.error(e.message || e) } }
async function upload({ file }) { if (uploading.value) return; uploading.value = true; try { await uploadMyResume(file); ElMessage.success('简历上传成功'); await load() } catch (e) { ElMessage.error(e.message || e) } finally { uploading.value = false } }
async function setPrimary(row) { try { await setMyPrimaryResume(row.id, resumes.value.find((item) => item.is_primary)?.id || row.id); ElMessage.success('主简历已更新'); await load() } catch (e) { ElMessage.error(e.message || e) } }
onMounted(load)
</script>
<style scoped>.card-head{display:flex;justify-content:space-between;align-items:center}.profile-form{display:grid;grid-template-columns:repeat(2,minmax(240px,1fr));column-gap:28px}.mt{margin-top:16px}@media(max-width:700px){.profile-form{display:block}}</style>
