const system = {
  url: '/mock/login',
  method: 'post',
  response: () => {
    return {
      code: 20000,
      jwtToken:"666666"
    }
  }
}

const loginOut = {
  url: '/mock/loginOut',
  method: 'post',
  response: () => {
    return {
      code: 200,
      title: 'mock request test'
    }
  }
}

export default [
  system,loginOut
]
