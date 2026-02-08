import React from 'react'
import jsep, { type Expression } from 'jsep'
import Nav from '../components/Nav'
import BottomNav from '../components/BottomNav'
import Hero from '../components/Hero'
import ProductCard from '../components/ProductCard'
import TaskCard from '../components/TaskCard'
import TimelineCard from '../components/TimelineCard'
import SimpleList from '../components/SimpleList'
import GridList from '../components/GridList'
import BasicForm from '../components/BasicForm'
import CheckoutForm from '../components/CheckoutForm'
import Button from '../components/Button'
import SectionHeader from '../components/SectionHeader'
import CartSummary from '../components/CartSummary'
import OrderSummary from '../components/OrderSummary'
import Footer from '../components/Footer'
import Breadcrumb from '../components/Breadcrumb'
import Tabs from '../components/Tabs'
import ConfirmModal from '../components/ConfirmModal'
import Toast from '../components/Toast'
import type { AssetRef } from '../types'

export interface PageSchema {
  slug: string
  title: string
  layout: 'default' | 'fullscreen' | 'sidebar'
  components: ComponentInstance[]
  head?: HeadMeta
}

export interface ComponentInstance {
  id: string
  key: string
  props: Record<string, PropValue>
  children?: ComponentInstance[]
  repeat?: RepeatBinding
  condition?: string
}

export interface PropValue {
  type: 'static' | 'binding' | 'asset'
  value: string | number | boolean | any[] | Record<string, any>
}

export interface RepeatBinding {
  source: string
  itemName: string
}

export interface HeadMeta {
  description?: string
  keywords?: string[]
  ogImage?: string
}

export interface SchemaDataContext {
  state: Record<string, any>
  records: Array<Record<string, any>>
  events: Array<Record<string, any>>
  tokens?: Record<string, any>
  assets?: AssetRegistry
  page?: PageSchema
}

export interface AssetRegistry {
  logo?: AssetRef
  style_refs?: AssetRef[]
  backgrounds?: AssetRef[]
  product_images?: AssetRef[]
  [key: string]: any
}

type ComponentEntry = {
  component: React.ComponentType<any>
  defaults?: Record<string, any>
}

const COMPONENT_MAP: Record<string, ComponentEntry> = {
  'nav-primary': { component: Nav },
  'nav-bottom': { component: BottomNav },
  'hero-banner': { component: Hero },
  'card-product': { component: ProductCard },
  'card-task': { component: TaskCard },
  'card-timeline': { component: TimelineCard },
  'list-simple': { component: SimpleList },
  'list-grid': { component: GridList },
  'form-basic': { component: BasicForm },
  'form-checkout': { component: CheckoutForm },
  'button-primary': { component: Button, defaults: { variant: 'primary' } },
  'button-secondary': { component: Button, defaults: { variant: 'secondary' } },
  'section-header': { component: SectionHeader },
  'cart-summary': { component: CartSummary },
  'order-summary': { component: OrderSummary },
  'footer-simple': { component: Footer },
  breadcrumb: { component: Breadcrumb },
  'tabs-basic': { component: Tabs },
  'modal-confirm': { component: ConfirmModal },
  'toast-message': { component: Toast },
}

const PARSED_CACHE = new Map<string, Expression>()
const DISALLOWED_MEMBERS = new Set(['__proto__', 'constructor', 'prototype'])

export function SchemaRenderer({ schema, data }: { schema: PageSchema; data: SchemaDataContext }) {
  return <>{schema.components.map((component) => renderComponent(component, data))}</>
}

export function renderComponent(instance: ComponentInstance, data: SchemaDataContext): React.ReactNode {
  if (instance.condition) {
    const visible = evaluateExpression(instance.condition, data)
    if (!visible) return null
  }

  const entry = COMPONENT_MAP[instance.id]
  if (!entry) {
    console.warn(`Unknown component: ${instance.id}`)
    return null
  }

  const renderWithData = (context: SchemaDataContext, keySuffix?: string) => {
    const resolvedProps = resolveProps(instance.props, context)
    const combinedProps = {
      ...entry.defaults,
      ...resolvedProps,
    }

    const children = instance.children?.map((child) => renderComponent(child, context))

    return (
      <entry.component key={`${instance.key}${keySuffix || ''}`} {...combinedProps}>
        {children}
      </entry.component>
    )
  }

  if (instance.repeat) {
    const items = evaluateExpression(instance.repeat.source, data)
    if (!Array.isArray(items)) return null

    return items.map((item, index) =>
      renderWithData(
        {
          ...data,
          [instance.repeat!.itemName]: item,
        },
        `-${index}`
      )
    )
  }

  return renderWithData(data)
}

export function resolveProps(props: Record<string, PropValue>, data: SchemaDataContext) {
  const resolved: Record<string, any> = {}

  Object.entries(props || {}).forEach(([key, value]) => {
    resolved[key] = resolvePropValue(value, data)
  })

  return resolved
}

function resolvePropValue(value: PropValue | any, data: SchemaDataContext): any {
  if (!value || typeof value !== 'object' || !('type' in value)) {
    return value
  }

  switch (value.type) {
    case 'static':
      return value.value
    case 'binding':
      return evaluateExpression(String(value.value ?? ''), data)
    case 'asset':
      return resolveAssetValue(value.value, data)
    default:
      return value.value
  }
}

function resolveAssetValue(value: any, data: SchemaDataContext) {
  if (value && typeof value === 'object' && 'url' in value) {
    return value.url
  }

  if (typeof value !== 'string') return value

  if (value.startsWith('asset:')) {
    const assetId = value
    const assets = data.assets || {}
    const resolved = findAssetById(assets, assetId)

    if (resolved?.url) return resolved.url

    const fallback = assetId.replace(/^asset:/, '')
    return `/assets/${fallback}`
  }

  return value
}

function findAssetById(registry: AssetRegistry, assetId: string): AssetRef | null {
  const candidates: Array<AssetRef | undefined> = []

  if (registry.logo) candidates.push(registry.logo)
  if (Array.isArray(registry.style_refs)) candidates.push(...registry.style_refs)
  if (Array.isArray(registry.backgrounds)) candidates.push(...registry.backgrounds)
  if (Array.isArray(registry.product_images)) candidates.push(...registry.product_images)

  const normalized = assetId.replace(/^asset:/, '')

  for (const asset of candidates) {
    if (!asset) continue
    if (asset.id === assetId || asset.id === `asset:${normalized}` || asset.id === normalized) {
      return asset
    }
  }

  return null
}

export function evaluateExpression(expression: string, data: Record<string, any>) {
  if (!expression) return undefined

  try {
    const parsed = PARSED_CACHE.get(expression) || jsep(expression)
    PARSED_CACHE.set(expression, parsed)
    return evaluateNode(parsed, data)
  } catch (error) {
    console.warn(`Failed to evaluate expression: ${expression}`, error)
    return undefined
  }
}

function evaluateNode(node: Expression, scope: Record<string, any>): any {
  switch (node.type) {
    case 'Literal':
      return node.value
    case 'Identifier':
      return scope[node.name]
    case 'MemberExpression':
      return evaluateMember(node, scope)
    case 'BinaryExpression':
      return evaluateBinary(node.operator, evaluateNode(node.left, scope), evaluateNode(node.right, scope))
    case 'LogicalExpression':
      return evaluateLogical(node.operator, evaluateNode(node.left, scope), evaluateNode(node.right, scope))
    case 'UnaryExpression':
      return evaluateUnary(node.operator, evaluateNode(node.argument, scope))
    case 'ConditionalExpression':
      return evaluateNode(node.test, scope)
        ? evaluateNode(node.consequent, scope)
        : evaluateNode(node.alternate, scope)
    case 'ArrayExpression':
      return node.elements.map((element) => (element ? evaluateNode(element, scope) : undefined))
    case 'ObjectExpression': {
      const properties = node.properties as any[]
      return Object.fromEntries(
        properties
          .filter((property) => property.type === 'Property')
          .map((property) => {
            const key =
              property.key.type === 'Identifier'
                ? property.key.name
                : String(evaluateNode(property.key, scope))
            return [key, evaluateNode(property.value, scope)]
          })
      )
    }
    default:
      return undefined
  }
}

function evaluateMember(node: any, scope: Record<string, any>) {
  const objectValue = evaluateNode(node.object, scope)
  if (objectValue == null) return undefined

  const propertyValue = node.computed
    ? evaluateNode(node.property, scope)
    : node.property.name

  if (typeof propertyValue !== 'string' && typeof propertyValue !== 'number') {
    return undefined
  }

  if (typeof propertyValue === 'string' && DISALLOWED_MEMBERS.has(propertyValue)) {
    return undefined
  }

  if (Array.isArray(objectValue) && propertyValue === 'length') {
    return objectValue.length
  }

  if (Object.prototype.hasOwnProperty.call(objectValue, propertyValue)) {
    return objectValue[propertyValue]
  }

  return undefined
}

function evaluateBinary(operator: string, left: any, right: any) {
  switch (operator) {
    case '+':
      return left + right
    case '-':
      return left - right
    case '*':
      return left * right
    case '/':
      return left / right
    case '%':
      return left % right
    case '==':
      return left == right
    case '!=':
      return left != right
    case '===':
      return left === right
    case '!==':
      return left !== right
    case '>':
      return left > right
    case '>=':
      return left >= right
    case '<':
      return left < right
    case '<=':
      return left <= right
    default:
      return undefined
  }
}

function evaluateLogical(operator: string, left: any, right: any) {
  switch (operator) {
    case '&&':
      return left && right
    case '||':
      return left || right
    default:
      return undefined
  }
}

function evaluateUnary(operator: string, value: any) {
  switch (operator) {
    case '!':
      return !value
    case '+':
      return +value
    case '-':
      return -value
    default:
      return undefined
  }
}
