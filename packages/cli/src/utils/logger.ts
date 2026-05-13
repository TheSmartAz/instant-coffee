import chalk from 'chalk'
import ora, { type Ora } from 'ora'
import Table from 'cli-table3'
import config from '../config.js'

export type LogLevel = 'info' | 'success' | 'warning' | 'error' | 'debug'

export class Logger {
  verbose: boolean

  constructor(verbose = config.verbose) {
    this.verbose = verbose
  }

  info(message: string): void {
    console.log(chalk.blue('i'), message)
  }

  success(message: string): void {
    console.log(chalk.green('OK'), message)
  }

  warning(message: string): void {
    console.log(chalk.yellow('WARN'), message)
  }

  error(message: string): void {
    console.error(chalk.red('ERROR'), message)
  }

  debug(message: string): void {
    if (this.verbose) {
      console.log(chalk.gray('debug'), chalk.gray(message))
    }
  }

  box(title: string, subtitle: string): void {
    const line = '-'.repeat(Math.max(title.length, subtitle.length) + 4)
    console.log()
    console.log(chalk.cyan(`+${line}+`))
    console.log(chalk.cyan('|'), chalk.bold(title), ' '.repeat(line.length - title.length - 1), chalk.cyan('|'))
    console.log(chalk.cyan('|'), subtitle, ' '.repeat(line.length - subtitle.length - 1), chalk.cyan('|'))
    console.log(chalk.cyan(`+${line}+`))
    console.log()
  }

  progress(text: string, percent = 0): Ora {
    return ora({
      text: `${text} ${percent}%`,
      color: 'cyan',
    })
  }

  table(headers: string[], rows: string[][]): void {
    const table = new Table({
      head: headers.map((header) => chalk.cyan(header)),
      style: {
        head: [],
        border: ['gray'],
      },
    })
    rows.forEach((row) => table.push(row))
    console.log(table.toString())
  }

  newLine(): void {
    console.log()
  }

  separator(): void {
    console.log(chalk.gray('-'.repeat(50)))
  }

  hint(command: string, description: string): void {
    console.log(chalk.gray('  Tip:'), chalk.white(command), chalk.gray(`- ${description}`))
  }
}

export default Logger
