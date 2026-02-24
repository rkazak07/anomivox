<template>
  <template v-if="!item.hidden">
    <template v-if="showSidebarItem(item.children, item)">
      <Link v-if="onlyOneChild.meta" :to="resolvePath(onlyOneChild.path)">
        <div :class="`sidebar-item ${isActived ? ' sidebar-item-active': ''}`">
          <el-icon style="margin: 10px 0" :color="isActived ? 'var(--el-menu-active-color)' : 'var(--el-menu-text-color)' " size="24">
            <component :is="onlyOneChild.meta?.elSvgIcon" />
          </el-icon>
          <span>{{ langTitle(onlyOneChild.meta?.title) }}</span>
        </div>
      </Link>
    </template>
  </template>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { resolve } from 'path-browserify'
import Link from './Link.vue'
import type { RouteRawConfig } from '~/basic'
import { isExternal } from '@/hooks/use-layout'
import { langTitle } from '@/hooks/use-common'

const props = defineProps({
  item: {
    type: Object,
    required: true
  },
  activePath: {
    type: String,
    default: ''
  },
  basePath: {
    type: String,
    default: ''
  }
})

const onlyOneChild = ref()
const showSidebarItem = (children = [], parent) => {
  const showingChildren = children.filter((item: RouteRawConfig) => {
    if (item.hidden) {
      return false
    } else {
      return true
    }
  })
  if (showingChildren.length > 0 && !parent?.alwaysShow) {
    onlyOneChild.value = showingChildren[0]
    return true
  }
  if (showingChildren.length === 0) {
    onlyOneChild.value = { ...parent, path: '', noChildren: true }
    return true
  }
  return false
}
const resolvePath = (routePath) => {
  if (isExternal(routePath)) {
    return routePath
  }
  if (isExternal(props.basePath)) {
    return props.basePath
  }
  return resolve(props.basePath, routePath)
}
const isActived = computed(() => {
  return props.activePath === resolvePath(onlyOneChild.value.path)
})
</script>

<style scoped lang="scss">
.sidebar-item {
  display: flex;
  align-items: center;
  cursor: pointer;
  flex-direction: column;
  transition: all 0.3s ease;
  margin-bottom: 16px;
  width: 72px;
  height: 72px;
  border-radius: 12px;
  background-color: transparent;
  
  &:hover {
    background-color: var(--el-menu-hover-bg-color);
    transform: translateY(-2px);
    
    span {
      color: var(--el-menu-hover-text-color);
    }
    .el-icon {
      color: var(--el-menu-hover-text-color) !important;
    }
  }
  
  span {
    font-size: 12px;
    color: var(--el-menu-text-color);
    text-align: center;
    font-weight: 500;
    transition: color 0.3s ease;
    margin-top: -4px;
  }
}
.sidebar-item-active {
  background-color: var(--el-menu-hover-bg-color) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  
  span {
    color: var(--el-menu-active-color);
    font-weight: 600;
  }
}
</style>
