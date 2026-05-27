# Learnings Log

Record of corrections, knowledge gaps, and best practices.

---

## [LRN-20260502-001] skill-install-vetting

**Logged**: 2026-05-02T09:15:00+08:00
**Priority**: high
**Status**: promoted
**Area**: config

### Summary
飞浪要求安装任何新 skill 前，必须先使用 skill-vetter 做安全检查。

### Details
避免直接安装来源不明的技能。每次安装前必须过 vetting protocol：
1. Source Check — 来源、作者、下载量
2. Code Review — 检查红标（curl到未知URL、读取敏感文件、base64、eval等）
3. Permission Scope — 评估文件/网络/命令权限
4. Risk Classification — 输出报告，高风险需人工确认

### Suggested Action
在 AGENTS.md 中固化此规则，每次安装新 skill 前自动触发 skill-vetter。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, skill-vetter/SKILL.md
- Tags: security, workflow, installation

---
