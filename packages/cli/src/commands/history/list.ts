import chalk from 'chalk'

export function displaySessionNotFound(sessionId: string): void {
  console.log()
  console.log(chalk.red.bold(`Session ${sessionId} was not found`))
  console.log()
  console.log(chalk.gray('Use this command to view sessions:'))
  console.log(chalk.cyan('   instant-coffee history'))
  console.log()
}
