import Vue from 'vue';
import _ from 'lodash';

import VueGroup from '../coms/vue-group.vue';
import VueNode from '../coms/vue-node.vue';

/**
 * Render component
 * @param {Object} item Component data (each item from mockdata)
 * @param {String} type Component rendering type
 * @param {Array} canvasNodes Canvas nodes for rendering
 */
const render = (item, type, parent = null, canvasNodes = null) => {

  let vueCon;

  if (item.render) {
    switch (typeof item.render) {
      case 'string':
        vueCon = Vue.extend({
          template: item.render,
          props:{
            itemData: {
              type: Object,
              required: true,
            }
          },
        });
        break;

      case 'object':
        vueCon = Vue.extend(item.render);
        break;

      default:
        throw Error(`${type} render property should be string or object type, now is ${typeof render}`);
    }
  } else {
    switch (type) {
      case 'group':
        vueCon = Vue.extend(VueGroup);
        break;

      case 'node':
        vueCon = Vue.extend(VueNode);
        break;

      default:
        break;
    }
    
  }

  let propsData = {
    itemData: item,
  }

  if (type === 'node') {
    let canvasNodeIndex = canvasNodes.findIndex((node)=>{
      return node.id === item.id;
    })
  
    if (canvasNodeIndex === -1) {
      console.warn(`Error in canvas.addNodes method`);
      return null;
    }
  
    let canvasNode = canvasNodes[canvasNodeIndex];

    propsData.canvasNode = canvasNode;
  
    const nodeCon = new vueCon({
      parent: parent,
      propsData
    });
    nodeCon.$butterfly = {
      type: type
    }
    // Temporarily not used for parent node emit support
    // nodeCon.$parent = parent
    // Enable component $emit event transmission
    nodeCon._events = parent._events;
    nodeCon.$mount();
    
    return nodeCon;
  }
  else {
    const Con = new vueCon({
      propsData
    })
    // Temporarily not used for parent edge and group emit support
    // Con.$parent = parent
    // Enable component $emit event transmission
    Con._events = parent._events;
    Con.$mount();
    
    return Con;
  }

};

const addCom = (proData) => {
  addGroupsCom(proData.groups);
  addNodesCom(proData.nodes);
};

const addGroupsCom = (canvasRoot, groups, parent) => {
  groups.map((item,index) => {
    const id = item.id;
    if (!id) {
      console.warn(`groups index ${index} does not contain ID property, please check format`);
      return;
    }

    const dom = canvasRoot.querySelector(`*[id^='bf_group_${item.id}']`);

    if (!dom) {
      return;
    }

    let groupCon = render(item, 'group', parent);

    dom.append(groupCon.$el);

  });
};

const addNodesCom = (canvasRoot, canvasNodes, nodes, parent) => {
  nodes.map((item,index) => {
    if (_.isArray(item)) {
      return ;
    }
    const id = item.id;
    if (!id) {
      console.warn(`nodes index ${index} does not contain ID property, please check format`);
      return;
    }

    const dom = canvasRoot.querySelector(`*[id^='bf_node_${item.id}']`);

    if (!dom) {
      return;
    }

    let nodeCon = render(item, 'node', parent, canvasNodes);

    dom.append(nodeCon.$el);

    // Need to mount anchor points first before adding anchor points
    let canvasNodeIndex = canvasNodes.findIndex((node)=>{
      return node.id === item.id;
    })
  
    if (canvasNodeIndex === -1) {
      console.warn(`Error in canvas.addNodes method`);
      return null;
    }
  })
};

const addEdgesCom = (canvasRoot, edges, parent) => {
  edges.map((item,index) => {
    const id = item.id;
    if (!id) {
      console.warn(`edges index ${index} does not contain ID property, please check format`);
      return;
    }

    if (item.render) {
      const dom = canvasRoot.querySelector(`*[id^='edge_label_${item.id}']`);

      if (!dom) {
        return;
      }

      let edgeCon = render(item, 'edge', parent);

      dom.append(edgeCon.$el);
    }
  })
};

export {
  addCom,
  addEdgesCom,
  addGroupsCom,
  addNodesCom
};
