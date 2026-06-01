module.exports = {
  plugins: {
    'postcss-pxtorem': {
      rootValue: 10,
      propList: ['*'],
      minPixelValue: 2,
      mediaQuery: false,
      selectorBlackList: [/^html$/],
    },
  },
}
