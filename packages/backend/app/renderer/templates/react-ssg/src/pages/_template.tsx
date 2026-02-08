import React from 'react'
import App from '../App'

export function createPage(slug: string) {
  const Page = () => <App pageSlug={slug} />
  return Page
}

const Page = createPage('__PAGE_SLUG__')

export default Page
