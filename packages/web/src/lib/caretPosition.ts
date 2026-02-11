export const getCaretCoords = (textarea: HTMLTextAreaElement, position: number) => {
  const style = window.getComputedStyle(textarea)
  const div = document.createElement('div')
  const properties = [
    'boxSizing',
    'width',
    'height',
    'overflowX',
    'overflowY',
    'borderTopWidth',
    'borderRightWidth',
    'borderBottomWidth',
    'borderLeftWidth',
    'paddingTop',
    'paddingRight',
    'paddingBottom',
    'paddingLeft',
    'fontStyle',
    'fontVariant',
    'fontWeight',
    'fontStretch',
    'fontSize',
    'fontSizeAdjust',
    'lineHeight',
    'fontFamily',
    'textAlign',
    'textTransform',
    'textIndent',
    'textDecoration',
    'letterSpacing',
    'wordSpacing',
    'tabSize',
  ] as const

  properties.forEach((prop) => {
    div.style[prop] = style[prop]
  })

  div.style.position = 'absolute'
  div.style.visibility = 'hidden'
  div.style.whiteSpace = 'pre-wrap'
  div.style.wordWrap = 'break-word'
  div.style.left = '-9999px'
  div.textContent = textarea.value.substring(0, position)

  const span = document.createElement('span')
  span.textContent = textarea.value.substring(position) || '.'
  div.appendChild(span)
  document.body.appendChild(div)

  const top = span.offsetTop
  const left = span.offsetLeft
  const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) || 16

  document.body.removeChild(div)

  return { top, left, lineHeight }
}
