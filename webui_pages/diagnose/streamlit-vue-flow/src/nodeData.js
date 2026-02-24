import titleContentNode from './node/title-content-node';
import agentGroupNode from './node/agent_group_node';
import Edge from './util/edge';

// Down: [0,1]
// Up: [0,-1]
// Right: [1,0]
// Left: [-1,0]

const data = {
  nodes: [
    {
      isRoot: true,
      id: 'A',
      userData: {
        title: 'Initialize Expert Roles',
        content: '',
        isCompleted: false,
        isRuning: false,
      },
      render: titleContentNode,
      top: 20,
      left: 120,
      endpoints: [
        {
          id: 'bottom',
          orientation: [0,1]
        }
      ]
    },
    {
      id: 'B',
      isRoot: true,
      userData: {
        title: 'Initialize Diagnosis Report',
        content: '',
        isCompleted: false,
        isRuning: false,
      },
      top: 150,
      left: 120,
      render: titleContentNode,
      endpoints: [
        {
          id: 'top',
          orientation: [0,-1]
        },
        {
          id: 'bottom',
          orientation: [0,1]
        }
      ]
    },
    {
      id: 'C',
      userData: {
        title: 'Assign Diagnosis Experts by Anomaly',
        content: '',
        isCompleted: false,
        isRuning: false,
      },
      top: 280,
      left: 120,
      render: titleContentNode,
      endpoints: [
        {
          id: 'top',
          orientation: [0,-1]
        },
        {
          id: 'bottom',
          orientation: [0,1]
        }
      ]
    },
    {
      id: 'D',
      userData: {
        title: 'Expert Diagnosis',
        content: '',
        isCompleted: false,
        isRuning: false,
        expertData: []
      },
      top: 410,
      left: 50,
      render: agentGroupNode,
      endpoints: [
        {
          id: 'top',
          orientation: [0,-1]
        },
        {
          id: 'bottom',
          orientation: [0,1]
        }
      ]
    },
    {
      id: 'E',
      userData: {
        title: 'Roundtable Discussion',
        content: '',
        isCompleted: false,
        isRuning: false
      },
      top: 610,
      left: 120,
      render: titleContentNode,
      endpoints: [
        {
          id: 'top',
          orientation: [0,-1]
        },
        {
          id: 'bottom',
          orientation: [0,1]
        }
      ]
    },
    {
      id: 'F',
      userData: {
        title: 'Generate Report',
        content: '',
        isCompleted: false,
        isRuning: false
      },
      top: 740,
      left: 120,
      render: titleContentNode,
      endpoints: [
        {
          id: 'top',
          orientation: [0,-1]
        }
      ]
    },
  ],
  edges: [
    {
      id: '1',
      source: 'bottom',
      target: 'top',
      sourceNode: 'A',
      targetNode: 'B',
      type: 'endpoint',
      Class: Edge
    },
    {
      id: '2',
      source: 'bottom',
      target: 'top',
      sourceNode: 'B',
      targetNode: 'C',
      type: 'endpoint',
      Class: Edge
    },
    {
      id: '3',
      source: 'bottom',
      target: 'top',
      sourceNode: 'C',
      targetNode: 'D',
      type: 'endpoint',
      Class: Edge
    },
    {
      id: '4',
      source: 'bottom',
      target: 'top',
      sourceNode: 'D',
      targetNode: 'E',
      type: 'endpoint',
      Class: Edge
    },
    {
      id: '5',
      source: 'bottom',
      target: 'top',
      sourceNode: 'E',
      targetNode: 'F',
      type: 'endpoint',
      Class: Edge
    }
  ]
};

export default data;
