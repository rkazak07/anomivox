import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '@/layout/index.vue'

export const constantRoutes = [
  {
    path: '/login',
    component: () => import('@/views/login/index.vue'),
    hidden: true
  },
  {
    path: '/404',
    component: () => import('@/views/error-page/404.vue'),
    hidden: true
  },
  {
    path: '/401',
    component: () => import('@/views/error-page/401.vue'),
    hidden: true
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: 'Dashboard', elSvgIcon: 'Monitor', affix: true }
      }
    ]
  },
  {
    path: '/chat',
    component: Layout,
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/chat/index.vue'),
        //using el svg icon, the elSvgIcon first when at the same time using elSvgIcon and icon
        meta: { title: 'Chat', elSvgIcon: 'ChatLineRound', affix: true }
      }
    ]
  },
  {
    path: '/knowledge/chat',
    component: Layout,
    children: [
      {
        path: '/knowledge/chat',
        name: 'KnowledgeChat',
        component: () => import('@/views/knowledge-chat/index.vue'),
        //using el svg icon, the elSvgIcon first when at the same time using elSvgIcon and icon
        meta: { title: 'KnowledgeChat', elSvgIcon: 'ChatLineSquare', affix: true }
      }
    ]
  },
  {
    path: '/diagnosis',
    component: Layout,
    children: [
      {
        path: '/diagnosis',
        name: 'Diagnosis',
        component: () => import('@/views/diagnosis/index.vue'),
        //using el svg icon, the elSvgIcon first when at the same time using elSvgIcon and icon
        meta: { title: 'Diagnosis', elSvgIcon: 'Odometer', affix: true }
      }
    ]
  },
  {
    path: '/reports',
    component: Layout,
    children: [
      {
        path: '/reports',
        name: 'Reports',
        component: () => import('@/views/reports/index.vue'),
        //using el svg icon, the elSvgIcon first when at the same time using elSvgIcon and icon
        meta: { title: 'Reports', elSvgIcon: 'DataBoard', affix: true }
      }
    ]
  },
  {
    path: '/knowledge',
    component: Layout,
    children: [
      {
        path: '/knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/index.vue'),
        //using el svg icon, the elSvgIcon first when at the same time using elSvgIcon and icon
        meta: { title: 'Knowledge', elSvgIcon: 'Notebook'}
      },
      {
        path: '/knowledge/detail',
        name: 'KnowledgeDetail',
        component: () => import('@/views/knowledge/detail.vue'),
        //using el svg icon, the elSvgIcon first when at the same time using elSvgIcon and icon
        meta: { title: 'Knowledge', elSvgIcon: 'Notebook', activeMenu: '/knowledge'}
      }
    ]
  },
  {
    path: '/scheduler',
    component: Layout,
    children: [
      {
        path: '/scheduler',
        name: 'Scheduler',
        component: () => import('@/views/scheduler/index.vue'),
        meta: { title: 'Scheduler', elSvgIcon: 'Clock' }
      }
    ]
  },
  {
    path: '/settings',
    component: Layout,
    children: [
      {
        path: '/settings',
        name: 'Settings',
        component: () => import('@/views/settings/index.vue'),
        meta: { title: 'Settings', elSvgIcon: 'Setting' }
      }
    ]
  },
  { path: "/:pathMatch(.*)", redirect: "/404", hidden: true }
]

export const roleCodeRoutes = [

]
/**
 * asyncRoutes
 * the routes that need to be dynamically loaded based on user roles
 */
export const asyncRoutes = [
  // 404 page must be placed at the end !!!
  { path: "/:pathMatch(.*)", redirect: "/404", hidden: true },
]


const router = createRouter({
  history: createWebHashHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: constantRoutes
})

export default router
