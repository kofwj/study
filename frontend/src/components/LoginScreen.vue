<script setup>
// 登录页：孩子/家长登录、注册新家、邀请码加入、找回码重置，以及家长首次改密。
// 两种用法：
//   <LoginScreen @ready="onReady" ref="loginRef" />        —— 未登录主界面
//   <LoginScreen mode="force-change" />                    —— 家长强制改密
// 组件挂载即重置为孩子登录态；登出后重新挂载自动回到默认。
import { reactive, ref } from 'vue'
import { Sun, Lock } from '@lucide/vue'
import { api } from '../api.js'
import { APP_LABEL, APP_REVISION } from '../version.js'
import { me, authed, isAdmin, mustChangePin, pendingRecovery, toast, showToast } from '../store.js'

const props = defineProps({ mode: { type: String, default: 'login' } })
const emit = defineEmits(['ready'])

const oldPin = ref('')
const newPin = ref('')
const newPin2 = ref('')
const pinForm = reactive({ who: 'kid', mode: 'login', account: '', val: '', name: '', family: '我家', code: '', recoverCode: '', recoverPin: '', recoverPin2: '' })

function goKidLogin() {
  pinForm.who = 'kid'
  pinForm.mode = 'login'
  pinForm.account = ''
  pinForm.val = ''
}
function goParentLogin() {
  pinForm.who = 'parent'
  pinForm.mode = 'login'
  pinForm.account = ''
  pinForm.val = ''
}
// 家长后台登出后要直接落到家长登录页：父级在重新挂载后调 show('parent')
function show(who) {
  if (who === 'parent') goParentLogin()
}
defineExpose({ show })

async function afterLogin(r) {
  if (r && r.recovery_code) pendingRecovery.value = r.recovery_code
  me.value = r
  pinForm.val = ''
  authed.value = true
  isAdmin.value = r.role === 'parent'
  mustChangePin.value = !!(r.force_pin_change && r.role === 'parent')
  emit('ready', r)
}
async function doChangePin() {
  const cur = oldPin.value.trim()
  const p = newPin.value.trim()
  if (!cur) { showToast('请输入当前密码'); return }
  if (p.length < 8) { showToast('家长密码至少 8 位'); return }
  if (p !== newPin2.value) { showToast('两次新密码不一致'); return }
  try {
    await api.admin.changePin(p, cur)
    mustChangePin.value = false
    oldPin.value = ''; newPin.value = ''; newPin2.value = ''
    me.value = await api.me().catch(() => me.value)
    showToast('密码已更新')
  } catch (e) { showToast(e.message) }
}
async function verifyPin() {
  try {
    if (pinForm.who === 'parent' && pinForm.mode === 'register') {
      await afterLogin(await api.register({ account: pinForm.account, pin: pinForm.val, name: pinForm.name, family_name: pinForm.family }))
    } else if (pinForm.who === 'parent' && pinForm.mode === 'join') {
      await afterLogin(await api.join({ account: pinForm.account, pin: pinForm.val, name: pinForm.name, code: pinForm.code }))
    } else if (pinForm.who === 'parent' && pinForm.mode === 'recover') {
      if (pinForm.recoverPin !== pinForm.recoverPin2) return showToast('两次新密码不一致')
      await afterLogin(await api.recover({ account: pinForm.account, code: pinForm.recoverCode, pin: pinForm.recoverPin }))
    } else {
      await afterLogin(await api.login(pinForm.account, pinForm.val))
    }
  } catch (e) { showToast(e.message) }
}
</script>

<template>
  <div class="login-screen">
    <div class="login-card">
      <!-- 家长强制改密 -->
      <template v-if="mode === 'force-change'">
        <div class="login-logo"><Lock class="ico" :size="36" /></div>
        <h1>改家长密码</h1>
        <input v-model="oldPin" type="password" placeholder="当前密码" autocomplete="current-password" />
        <input v-model="newPin" type="password" placeholder="新密码（至少 8 位）" autocomplete="new-password" />
        <input v-model="newPin2" type="password" placeholder="再输一遍确认" autocomplete="new-password" @keyup.enter="doChangePin" />
        <button class="login-enter" @click="doChangePin">保存新密码</button>
        <p v-if="toast" class="login-note danger">{{ toast }}</p>
      </template>

      <!-- 登录主界面 -->
      <template v-else>
        <div class="login-logo"><Sun class="ico" :size="36" /></div>
        <h1>阳光学习工作台</h1>
        <p class="login-ver" :title="APP_REVISION">{{ APP_LABEL }}</p>

        <template v-if="pinForm.who === 'kid'">
          <input v-model="pinForm.account" placeholder="孩子账号" autocomplete="username" />
          <input v-model="pinForm.val" type="password" placeholder="孩子密码（至少 6 位）" autocomplete="current-password" @keyup.enter="verifyPin" />
          <button class="login-enter" @click="verifyPin">进入</button>
          <button type="button" class="login-switch" @click="goParentLogin">我是家长</button>
        </template>

        <template v-else>
          <div class="login-tabs">
            <button type="button" :class="{ on: pinForm.mode==='login' }" @click="pinForm.mode='login'">登录</button>
            <button type="button" :class="{ on: pinForm.mode==='register' }" @click="pinForm.mode='register'">注册新家</button>
            <button type="button" :class="{ on: pinForm.mode==='join' }" @click="pinForm.mode='join'">邀请码加入</button>
          </div>
          <template v-if="pinForm.mode !== 'recover'">
            <input v-model="pinForm.account" placeholder="家长账号" autocomplete="username" />
            <input v-model="pinForm.val" type="password" :placeholder="pinForm.mode==='login' ? '家长密码' : '家长密码至少 8 位'" autocomplete="current-password" @keyup.enter="verifyPin" />
            <input v-if="pinForm.mode!=='login'" v-model="pinForm.name" placeholder="你的名字" />
            <input v-if="pinForm.mode==='register'" v-model="pinForm.family" placeholder="家庭名（如：乐乐的家）" />
            <input v-if="pinForm.mode==='join'" v-model="pinForm.code" placeholder="邀请码" />
            <button class="login-enter" @click="verifyPin">{{ pinForm.mode==='register' ? '注册并进入' : '进入' }}</button>
            <button v-if="pinForm.mode==='login'" type="button" class="login-switch" @click="pinForm.mode='recover'">忘记密码</button>
          </template>
          <template v-else>
            <input v-model="pinForm.account" placeholder="家长账号" autocomplete="username" />
            <input v-model="pinForm.recoverCode" placeholder="10 位找回码" autocomplete="off" />
            <input v-model="pinForm.recoverPin" type="password" placeholder="新密码（至少 8 位）" autocomplete="new-password" />
            <input v-model="pinForm.recoverPin2" type="password" placeholder="再输一遍新密码" autocomplete="new-password" @keyup.enter="verifyPin" />
            <button class="login-enter" @click="verifyPin">重置密码并进入</button>
            <button type="button" class="login-switch" @click="pinForm.mode='login'">回到登录</button>
          </template>
          <button type="button" class="login-switch" @click="goKidLogin">孩子打卡入口</button>
        </template>
        <p v-if="toast" class="login-note danger">{{ toast }}</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.login-screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; background: var(--bg); }
.login-card { background: var(--surface); border-radius: var(--radius-lg); padding: 32px 28px; width: 92%; max-width: 380px; box-shadow: var(--shadow-md); text-align: center; }
.login-logo { width: 72px; height: 72px; margin: 0 auto 14px; border-radius: var(--radius-circle); background: var(--warm); color: var(--accent); display: flex; align-items: center; justify-content: center; }
.login-card h1 { font-size: 22px; margin: 0 0 4px; }
.login-tabs { display: flex; gap: 4px; margin-bottom: 16px; background: var(--surface-2); border-radius: var(--radius-pill); padding: 4px; }
.login-tabs button { flex: 1; border: none; background: none; padding: 8px 4px; border-radius: var(--radius-pill); font-size: 13px; color: var(--ink-2); cursor: pointer; font-weight: 700; }
.login-tabs button.on { background: var(--surface); color: var(--brand-deep); box-shadow: var(--shadow-sm); }
.login-card input { width: 100%; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius-md); font-size: 15px; margin-bottom: 10px; box-sizing: border-box; font-family: inherit; }
.login-enter { width: 100%; border: none; background: var(--brand); color: #fff; border-radius: var(--radius-md); padding: 12px; font-weight: 800; font-size: 15px; cursor: pointer; margin-top: 2px; font-family: inherit; }
.login-note { font-size: 12px; color: var(--ink-3); margin: 12px 0 0; line-height: 1.5; }
.login-ver { margin: -8px 0 14px; color: var(--ink-3); font-size: 12px; font-weight: 700; }
.login-switch {
  display: block; width: 100%; margin-top: 10px; border: none; background: none;
  color: var(--ink-3); font-size: 13px; font-weight: 700; cursor: pointer; font-family: inherit;
}
</style>
