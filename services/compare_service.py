"""
比对服务
报告表内容与反馈信息的比对分析
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import uuid
from datetime import datetime


class CompareService:
    """比对服务"""

    def __init__(self):
        pass

    def compare(
        self,
        report_data: Dict[str, Any],
        feedback_data: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        执行比对分析

        Args:
            report_data: 报告表 OCR 识别结果
            feedback_data: 反馈信息（按章节分组）

        Returns:
            比对结果
        """
        compare_id = str(uuid.uuid4())

        # 比对各章节
        diff_items = []
        stats = {
            "total": 0,
            "consistent": 0,
            "inconsistent": 0,
            "missing": 0,
            "extra": 0
        }

        # 按章节逐一比对
        for chapter, report_fields in report_data.items():
            feedback_items = feedback_data.get(chapter, [])

            if not feedback_items:
                # 报告表有数据，但反馈无对应章节
                if report_fields:
                    diff_items.append({
                        "chapter": chapter,
                        "type": "extra_in_report",
                        "description": "报告表有数据，但反馈无对应信息",
                        "report_data": report_fields,
                        "feedback_data": None
                    })
                    stats["extra"] += 1
                    stats["total"] += 1
                continue

            # 执行比对
            chapter_diffs = self._compare_chapter(
                chapter, report_fields, feedback_items
            )
            diff_items.extend(chapter_diffs)

            # 更新统计
            for diff in chapter_diffs:
                stats["total"] += 1
                if diff["result"] == "一致":
                    stats["consistent"] += 1
                elif diff["result"] == "不一致":
                    stats["inconsistent"] += 1
                elif diff["result"] == "缺失":
                    stats["missing"] += 1

        # 生成摘要
        summary = {
            "compare_id": compare_id,
            "compare_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "statistics": stats,
            "consistency_rate": (
                f"{stats['consistent'] / stats['total'] * 100:.1f}%"
                if stats["total"] > 0 else "N/A"
            )
        }

        return {
            "compare_id": compare_id,
            "summary": summary,
            "diff_items": diff_items,
            "feedback_data": feedback_data
        }

    def _compare_chapter(
        self,
        chapter: str,
        report_fields: Dict,
        feedback_items: List[Dict]
    ) -> List[Dict]:
        """
        比对单个章节

        Args:
            chapter: 章节名称
            report_fields: 报告表字段
            feedback_items: 反馈数据列表

        Returns:
            差异列表
        """
        diffs = []

        # 根据章节类型选择比对策略
        if chapter in ["境内房产", "境外房产"]:
            diffs = self._compare_property(report_fields, feedback_items, chapter)
        elif chapter in ["境内基金", "境外基金"]:
            diffs = self._compare_fund(report_fields, feedback_items, chapter)
        elif chapter in ["境内投资型保险", "境外投资型保险"]:
            diffs = self._compare_insurance(report_fields, feedback_items, chapter)
        elif chapter in ["本人护照"]:
            diffs = self._compare_passport(report_fields, feedback_items, chapter)
        elif chapter in ["港澳台通行证"]:
            diffs = self._compare_pass_card(report_fields, feedback_items, chapter)
        elif chapter in ["投资企业"]:
            diffs = self._compare_company(report_fields, feedback_items, chapter)
        else:
            # 通用比对：简单字段匹配
            diffs = self._compare_generic(report_fields, feedback_items, chapter)

        return diffs

    def _compare_property(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """比对房产信息"""
        diffs = []

        # 提取报告表中的房产信息
        report_properties = report_fields.get("properties", [])

        # 匹配比对
        for i, report_prop in enumerate(report_properties):
            matched = False
            report_address = report_prop.get("地址", "")

            for fb_item in feedback_items:
                fb_address = fb_item.get("地址", "")

                # 地址相似度比对（简化版）
                if self._is_similar(report_address, fb_address):
                    matched = True
                    # 比对面积
                    report_area = report_prop.get("面积", 0)
                    fb_area = fb_item.get("面积", 0)

                    if abs(float(report_area or 0) - float(fb_area or 0)) > 0.1:
                        diffs.append({
                            "chapter": chapter,
                            "index": i + 1,
                            "field": "面积",
                            "report_value": report_area,
                            "feedback_value": fb_area,
                            "result": "不一致"
                        })
                    else:
                        diffs.append({
                            "chapter": chapter,
                            "index": i + 1,
                            "field": "面积",
                            "report_value": report_area,
                            "feedback_value": fb_area,
                            "result": "一致"
                        })
                    break

            if not matched:
                diffs.append({
                    "chapter": chapter,
                    "index": i + 1,
                    "field": "地址",
                    "report_value": report_address,
                    "feedback_value": None,
                    "result": "缺失"
                })

        return diffs

    def _compare_fund(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """比对基金信息"""
        diffs = []

        report_funds = report_fields.get("funds", [])

        for i, report_fund in enumerate(report_funds):
            matched = False
            report_name = report_fund.get("基金名称", "")

            for fb_item in feedback_items:
                fb_name = fb_item.get("基金名称", "")

                if self._is_similar(report_name, fb_name):
                    matched = True
                    # 比对份额和净值
                    report_share = report_fund.get("份额", 0)
                    fb_share = fb_item.get("份额", 0)

                    if float(report_share or 0) != float(fb_share or 0):
                        diffs.append({
                            "chapter": chapter,
                            "index": i + 1,
                            "field": "份额",
                            "report_value": report_share,
                            "feedback_value": fb_share,
                            "result": "不一致"
                        })
                    else:
                        diffs.append({
                            "chapter": chapter,
                            "index": i + 1,
                            "field": "份额",
                            "report_value": report_share,
                            "feedback_value": fb_share,
                            "result": "一致"
                        })
                    break

            if not matched:
                diffs.append({
                    "chapter": chapter,
                    "index": i + 1,
                    "field": "基金名称",
                    "report_value": report_name,
                    "feedback_value": None,
                    "result": "缺失"
                })

        return diffs

    def _compare_insurance(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """比对保险信息"""
        diffs = []

        report_insurance = report_fields.get("insurance", [])

        for i, report_ins in enumerate(report_insurance):
            matched = False
            report_policy = report_ins.get("保单号", "")

            for fb_item in feedback_items:
                fb_policy = fb_item.get("保单号", "")

                if report_policy and fb_policy and self._is_similar(report_policy, fb_policy):
                    matched = True
                    # 比对保费
                    report_premium = report_ins.get("累计保费", 0)
                    fb_premium = fb_item.get("累计保费", 0)

                    if abs(float(report_premium or 0) - float(fb_premium or 0)) > 0.01:
                        diffs.append({
                            "chapter": chapter,
                            "index": i + 1,
                            "field": "累计保费",
                            "report_value": report_premium,
                            "feedback_value": fb_premium,
                            "result": "不一致"
                        })
                    break

            if not matched:
                diffs.append({
                    "chapter": chapter,
                    "index": i + 1,
                    "field": "保单号",
                    "report_value": report_policy,
                    "feedback_value": None,
                    "result": "缺失"
                })

        return diffs

    def _compare_passport(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """比对护照信息"""
        diffs = []

        report_passports = report_fields.get("passports", [])

        for i, report_pass in enumerate(report_passports):
            matched = False
            report_no = report_pass.get("护照号码", "")

            for fb_item in feedback_items:
                fb_no = fb_item.get("护照号码", "")

                if report_no and fb_no and self._is_similar(report_no, fb_no):
                    matched = True
                    break

            if not matched:
                diffs.append({
                    "chapter": chapter,
                    "index": i + 1,
                    "field": "护照号码",
                    "report_value": report_no,
                    "feedback_value": None,
                    "result": "缺失"
                })

        return diffs

    def _compare_pass_card(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """比对通行证信息"""
        diffs = []

        report_cards = report_fields.get("cards", [])

        for i, report_card in enumerate(report_cards):
            matched = False
            report_no = report_card.get("证件号码", "")

            for fb_item in feedback_items:
                fb_no = fb_item.get("证件号码", "")

                if report_no and fb_no and self._is_similar(report_no, fb_no):
                    matched = True
                    break

            if not matched:
                diffs.append({
                    "chapter": chapter,
                    "index": i + 1,
                    "field": "证件号码",
                    "report_value": report_no,
                    "feedback_value": None,
                    "result": "缺失"
                })

        return diffs

    def _compare_company(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """比对投资企业信息"""
        diffs = []

        report_companies = report_fields.get("companies", [])

        for i, report_comp in enumerate(report_companies):
            matched = False
            report_name = report_comp.get("企业名称", "")

            for fb_item in feedback_items:
                fb_name = fb_item.get("企业名称", "")

                if self._is_similar(report_name, fb_name):
                    matched = True
                    # 比对认缴出资额
                    report_amount = report_comp.get("认缴出资额", 0)
                    fb_amount = fb_item.get("认缴出资额", 0)

                    if abs(float(report_amount or 0) - float(fb_amount or 0)) > 0.01:
                        diffs.append({
                            "chapter": chapter,
                            "index": i + 1,
                            "field": "认缴出资额",
                            "report_value": report_amount,
                            "feedback_value": fb_amount,
                            "result": "不一致"
                        })
                    break

            if not matched:
                diffs.append({
                    "chapter": chapter,
                    "index": i + 1,
                    "field": "企业名称",
                    "report_value": report_name,
                    "feedback_value": None,
                    "result": "缺失"
                })

        return diffs

    def _compare_generic(
        self,
        report_fields: Dict,
        feedback_items: List[Dict],
        chapter: str
    ) -> List[Dict]:
        """通用比对"""
        diffs = []

        # 简单比对：报告表有数据，反馈无数据
        if report_fields and not feedback_items:
            diffs.append({
                "chapter": chapter,
                "field": "整体",
                "report_value": "有数据",
                "feedback_value": None,
                "result": "缺失"
            })

        return diffs

    def _is_similar(self, str1: str, str2: str, threshold: float = 0.7) -> bool:
        """
        判断两个字符串是否相似（简化版）

        Args:
            str1: 字符串1
            str2: 字符串2
            threshold: 相似度阈值

        Returns:
            是否相似
        """
        if not str1 or not str2:
            return False

        str1 = str(str1).strip().upper()
        str2 = str(str2).strip().upper()

        # 完全相等
        if str1 == str2:
            return True

        # 包含关系
        if str1 in str2 or str2 in str1:
            return True

        # 简单相似度计算
        common = sum(1 for a, b in zip(str1, str2) if a == b)
        similarity = common / max(len(str1), len(str2), 1)

        return similarity >= threshold

    def save_result(self, compare_result: Dict[str, Any], output_dir: Path) -> Path:
        """
        保存比对结果

        Args:
            compare_result: 比对结果
            output_dir: 输出目录

        Returns:
            结果文件路径
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        compare_id = compare_result.get("compare_id", "unknown")
        output_file = output_dir / f"compare_{compare_id}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(compare_result, f, ensure_ascii=False, indent=2)

        return output_file
