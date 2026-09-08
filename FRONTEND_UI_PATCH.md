# 前端UI权限控制补丁

## 需要修改的地方

由于前端文件较大（1200+行），以下是需要手动调整UI权限的关键位置：

### 1. 家长成员管理（members section）

找到删除家长成员的按钮，添加权限判断：

```vue
<!-- 修改前 -->
<button @click="delMember(m.id)">删除</button>

<!-- 修改后 -->
<button v-if="isOwner" @click="delMember(m.id)" class="text-red-600">删除</button>
<span v-else class="text-gray-400 text-sm" title="需要创建者权限">仅创建者</span>
```

### 2. 孩子账号管理（kids section）

找到删除孩子账号的按钮：

```vue
<!-- 修改前 -->
<button @click="delKid(k.id)">删除</button>

<!-- 修改后 -->
<button v-if="isOwner" @click="delKid(k.id)" class="text-red-600">删除</button>
<span v-else class="text-gray-400 text-sm" title="需要创建者权限">仅创建者</span>
```

### 3. 邀请码管理（invites section）

找到生成邀请码和删除邀请码的按钮：

```vue
<!-- 生成邀请码按钮 -->
<button v-if="isOwner" @click="createInvite" class="btn-primary">生成新邀请码</button>
<div v-else class="text-gray-500 text-sm">需要创建者权限才能生成邀请码</div>

<!-- 删除邀请码按钮 -->
<button v-if="isOwner" @click="delInvite(code)">删除</button>
<span v-else class="text-gray-400 text-sm">仅创建者</span>
```

### 4. 邀请保护设置

找到"邀请码保护"开关：

```vue
<!-- 修改前 -->
<input type="checkbox" v-model="inviteProtect" @change="saveInviteProtect">

<!-- 修改后 -->
<input type="checkbox" v-model="inviteProtect" @change="saveInviteProtect" :disabled="!isOwner">
<span v-if="!isOwner" class="text-sm text-gray-500 ml-2">需要创建者权限</span>
```

### 5. 添加转让权限功能（可选）

在家长成员列表中，为创建者添加"转让权限"按钮：

```vue
<div v-if="section === 'members'" class="space-y-4">
  <div v-for="m in members" :key="m.id" class="flex items-center justify-between border-b pb-2">
    <div>
      <div class="font-medium">{{ m.name }}</div>
      <div class="text-sm text-gray-500">{{ m.account }}</div>
      <!-- 显示角色标记 -->
      <span v-if="m.id === me.id && me.parent_role === 'owner'" class="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
        创建者
      </span>
    </div>
    <div class="space-x-2">
      <!-- 转让权限按钮（只有创建者能看到，且不能对自己操作） -->
      <button 
        v-if="isOwner && m.id !== me.id" 
        @click="transferOwner(m)"
        class="text-blue-600 text-sm"
      >
        转让创建者
      </button>
      
      <!-- 删除按钮 -->
      <button 
        v-if="isOwner && m.id !== me.id" 
        @click="delMember(m.id)"
        class="text-red-600 text-sm"
      >
        删除
      </button>
      <span v-if="!isOwner" class="text-gray-400 text-sm">仅创建者可操作</span>
    </div>
  </div>
</div>
```

### 6. 添加转让权限的方法

在 `<script setup>` 中添加：

```javascript
async function transferOwner(member) {
  if (!confirm(`确定要将创建者权限转让给"${member.name}"吗？转让后您将成为普通成员。`)) return
  try {
    await api.admin.transferOwner(member.id)
    showToast(`已将创建者权限转让给 ${member.name}`)
    await load()  // 重新加载数据
  } catch (e) {
    showToast(e.message)
  }
}
```

### 7. API 方法添加

在 `frontend/src/api.js` 的 `api.admin` 中添加：

```javascript
transferOwner: (new_owner_id) => j('/api/admin/transfer-owner', { method: 'POST', ...body({ new_owner_id }) }),
```

## 简化方案（如果觉得麻烦）

如果觉得手动修改太多，可以只做最简单的处理：

1. 在每个需要权限的按钮上添加 `v-if="isOwner"`
2. 对于普通成员，显示灰色文字"仅创建者可操作"

这样至少保证了后端权限控制（最重要），前端只是隐藏UI提升体验。

## 测试建议

1. 用创建者账号登录，确认能看到所有按钮
2. 创建第二个家长账号（通过邀请码）
3. 用第二个家长账号登录，确认删除/邀请按钮不可见
4. 测试转让权限功能
5. 转让后，原创建者应该看不到这些按钮了
