import ts from 'typescript'
import fs from 'node:fs'
import vm from 'node:vm'
import assert from 'node:assert/strict'
const exports = {}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('../packages/joint-command/frontend/companyOrders.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, { exports })
const sheets = [{ key:'19_已完成订单明细', headers:['销售项目编码','销售项目名称','项目归属','签订时间','销售合同金额'], rows:[['A','项目A','东区','2026-01-02',10000],['A','项目A','东区','2026-02-03',20000],['B','项目B','西区','2025-01-01',90000],['C','项目C','中区','无日期',100]] }]
const result = exports.companyOrders(sheets, 2026)
assert.equal(result.months.length, 12)
assert.equal(result.months[0].order, 1)
assert.equal(result.months[1].order, 2)
assert.equal(result.months[0].managed, null)
assert.equal(result.top.length, 1)
assert.equal(result.top[0].amount, 3)
assert.equal(result.top[0].months, '1、2月')
assert.equal(result.invalidDates, 1)
console.log('company orders: passed')
const receipts = exports.companyReceipts([
  { key: '实际回款明细', headers: ['项目编码','项目名称','区域','回款日期','实际回款金额（元）'], rows: [['A','项目A','东区','2026-01-01',10000],['A','项目A','东区','2026-02-01',20000],['B','项目B','西区','2025-01-01',990000]] },
  { key: '回款任务令', headers: ['项目名称','回款时间','本月计划回款金额'], rows: [['计划','2026-01-01',900000]] },
], 2026)
assert.equal(receipts.months[0].order, 1)
assert.equal(receipts.months[1].order, 2)
assert.equal(receipts.top[0].amount, 3)
assert.equal(receipts.top[0].months, '1、2月')
assert.equal(receipts.top.length, 1)
assert.equal(exports.companyReceipts([],2026).months[0].order, null)
console.log('company receipts: passed')
const ranked = exports.companyOrders([{ ...sheets[0], rows: [...sheets[0].rows, ['OTHER','其他','公司其他','2026-03-01',9999999], ['UNKNOWN','待核验','','2026-03-02',8888888], ['GD','广东项目','广东区','2026-04-01',10000]] }], 2026)
assert.equal(ranked.top.length, 2)
assert.equal(ranked.rankingTotal, 4)
assert.equal(ranked.topTotal, 4)
assert.equal(ranked.excludedProjects, 2)
assert.equal(ranked.cutoffMonth, 4)
assert.equal(ranked.top[1].region, '广东')
assert.equal(exports.companyCashFlow([], 2026).total, null)
const cash = exports.companyCashFlow([{key:'公司月度现金流',headers:['年份','月份','经营现金流（万元）'],rows:[[2026,1,10],[2026,2,-4],[2026,3,5],[2026,3,6],[2025,4,999]]}],2026)
assert.equal(cash.total, 6)
assert.equal(cash.count, 2)
assert.equal(cash.positive, 1)
assert.equal(cash.negative, 1)
console.log('PASS four-region TOP10 scope, summaries and missing/duplicate cash-flow safeguards')
