<template>
  <el-breadcrumb class="app-breadcrumb" separator="/">
    <!--  mainNeedAnimation: controls whether this breadcrumb needs animation  -->
    <transition-group v-if="settings.mainNeedAnimation" name="breadcrumb">
      <!--  Generate breadcrumbs from filtered array  -->
      <el-breadcrumb-item v-for="(item, index) in levelList" :key="item.path">
        <span v-if="item.redirect === 'noRedirect' || index === levelList.length - 1" class="no-redirect">
          {{ langTitle(item.meta?.title) }}
        </span>
        <a v-else @click.prevent="handleLink(item)">{{ langTitle(item.meta?.title) }}</a>
      </el-breadcrumb-item>
    </transition-group>
    <!--no transition-->
    <template v-else>
      <el-breadcrumb-item v-for="(item, index) in levelList" :key="item.path">
        <span v-if="item.redirect === 'noRedirect' || index === levelList.length - 1" class="no-redirect">
          {{ langTitle(item.meta?.title) }}
        </span>
        <a v-else @click.prevent="handleLink(item)">{{ langTitle(item.meta?.title) }}</a>
      </el-breadcrumb-item>
    </template>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { compile } from 'path-to-regexp'
import { useRoute, useRouter } from 'vue-router'
import type { RouterTypes } from '~/basic'
import { useBasicStore } from '@/store/basic'
import { langTitle } from '@/hooks/use-common'
const levelList = ref()
const { settings } = useBasicStore()
const route = useRoute()
const getBreadcrumb = () => {
  // only show routes with has  meta.title
  let matched: RouterTypes = route.matched.filter((item) => item.meta?.title)
  const isHasDashboard = matched[0]?.name?.toLocaleLowerCase() === 'Dashboard'.toLocaleLowerCase()
  if (!isHasDashboard) {
    matched = [{ path: '/dashboard', meta: { title: 'Dashboard' } }].concat(matched)
  }
  levelList.value = matched.filter((item) => item.meta && item.meta.title && item.meta.breadcrumb !== false)
}

//const  toPath =  compile ( "/user/:id" ,  {  encode : encodeURIComponent  } ) ;
//toPath ( {  id : 123  } ) ; //=> "/user/123"
const pathCompile = (path) => {
  const { params } = route
  const toPath = compile(path)
  return toPath(params)
}
const router = useRouter()
const handleLink = (item) => {
  const { redirect, path } = item
  if (redirect) {
    router.push(redirect)
    return
  }
  if (path) router.push(pathCompile(path))
}
watch(
  () => route.path,
  () => getBreadcrumb(),
  { immediate: true }
)
</script>

<style lang="scss" scoped>
.app-breadcrumb.el-breadcrumb {
  display: inline-block;
  font-size: 14px;
  line-height: 50px;
  margin-left: 8px;

  .no-redirect {
    color: var(--breadcrumb-no-redirect);
    cursor: text;
  }
}
</style>
