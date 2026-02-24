import ButterflyVue from './butterfly-vue.vue';
import ButterflyVueEndpoint from './coms/vue-endpoint.vue';

const install = (Vue)=>{
  Vue.component(ButterflyVue.name, ButterflyVue);
  Vue.component(ButterflyVueEndpoint.name, ButterflyVueEndpoint);
}

// Default export component
export default {
  install,
  ButterflyVue,
  ButterflyVueEndpoint
};

export {
  ButterflyVue,
  ButterflyVueEndpoint
}
