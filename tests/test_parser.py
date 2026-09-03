from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from database import SeminarDatabase
from parser import missing_required_fields, parse_seminar


CRRC_MESSAGE = """🌟 中车戚墅堰所2027届校园招聘宣讲会来啦！！
⏰ 宣讲时间：9月9日 18:00-21:30
📍 宣讲地点：大连理工大学 综合教学2号楼A202
🔗 专属宣讲群链接：[https://s.51job.com/1OXOUd](https://s.51job.com/1OXOUd)
🔗 立即网申：[https://crrc-qsys.hotjob.cn/](https://crrc-qsys.hotjob.cn/)
"""

AECC_MESSAGE = """【今晚6:00  综二A201】📣中国航发黎明2027届秋招宣讲会进校啦
本硕博均可投递，五险二金
📝网申：[https://s.iguopin.com/hflm](https://s.iguopin.com/hflm)
"""

GHSMC_MESSAGE = """[庆祝]【积微成著 山海可平】[庆祝]
杭州积海-大连理工大学站宣讲会来啦！
宣讲时间：9月10日（周四）13：00-15：00👈
宣讲地点：陵水校区综合教学2号楼A401👈
杭州积海半导体有限公司总部位于浙江省杭州市钱塘区。
【校招官微】：[https://ghsmc.zhiye.com/campus](https://ghsmc.zhiye.com/campus)
或搜索微信公众号【杭州积海半导体】
"""

XIAOHE_MESSAGE = """晓禾教育2026年秋季校园招聘首场空中宣讲会来喽~
🕒时间：9月4日（周五）15：00
📍地点：
#腾讯会议：387-429-047
#腾讯会议：655-100-665（两个会议号都可参加空宣）
【工作地点】：武汉、郑州、襄阳、宜昌
📬【简历投递】
1. 网申：[https://jsj.top/f/cqeQqJ](https://jsj.top/f/cqeQqJ)
2.邮箱：jobs@example.com
联系人：王老师 000-0000-0000（示例号码）
"""


class ParserTests(unittest.TestCase):
    def test_crrc_message(self) -> None:
        item = parse_seminar(CRRC_MESSAGE, date(2026, 9, 3))
        self.assertEqual(item.company, "中车戚墅堰所")
        self.assertEqual(item.event_date, date(2026, 9, 9))
        self.assertEqual((item.start_time, item.end_time), ("18:00", "21:30"))
        self.assertEqual(item.location, "综合教学2号楼A202")
        self.assertEqual([entry.label for entry in item.applications], ["群链接", "网申"])
        self.assertEqual(missing_required_fields(item), [])

    def test_relative_tonight_and_heading_location(self) -> None:
        item = parse_seminar(AECC_MESSAGE, date(2026, 9, 8))
        self.assertEqual(item.company, "中国航发黎明")
        self.assertEqual(item.event_date, date(2026, 9, 8))
        self.assertEqual(item.start_time, "18:00")
        self.assertEqual(item.location, "综二A201")

    def test_full_legal_name_enriches_short_title(self) -> None:
        item = parse_seminar(GHSMC_MESSAGE, date(2026, 9, 3))
        self.assertEqual(item.company, "杭州积海半导体")
        self.assertEqual(item.event_date, date(2026, 9, 10))
        self.assertEqual((item.start_time, item.end_time), ("13:00", "15:00"))
        self.assertEqual(item.location, "陵水校区综合教学2号楼A401")
        self.assertTrue(any(entry.label == "校招官微" for entry in item.applications))
        self.assertTrue(any(entry.label == "公众号" for entry in item.applications))

    def test_online_seminar_keeps_all_meetings_and_application_methods(self) -> None:
        item = parse_seminar(XIAOHE_MESSAGE, date(2026, 9, 3))
        self.assertEqual(item.company, "晓禾教育")
        self.assertEqual(item.event_date, date(2026, 9, 4))
        self.assertEqual(item.start_time, "15:00")
        self.assertEqual(item.location, "腾讯会议：387-429-047")
        self.assertEqual(item.meetings, ["387-429-047", "655-100-665"])
        self.assertTrue(any(entry.value == "https://jsj.top/f/cqeQqJ" for entry in item.applications))
        self.assertTrue(any(entry.value == "jobs@example.com" for entry in item.applications))
        self.assertTrue(any(entry.label == "联系人" for entry in item.applications))

    def test_missing_required_fields_are_reported(self) -> None:
        item = parse_seminar("某公司招聘，欢迎投递简历", date(2026, 9, 3))
        self.assertEqual(missing_required_fields(item), ["企业", "日期", "开始时间", "地点"])


class DatabaseTests(unittest.TestCase):
    def test_crud_ranges_history_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SeminarDatabase(Path(directory) / "test.db")
            item = parse_seminar(CRRC_MESSAGE, date(2026, 9, 3))
            item_id = database.add(item)
            self.assertEqual(len(database.between(date(2026, 9, 3), date(2026, 9, 17))), 1)
            self.assertEqual(len(database.duplicates(item)), 0)
            duplicate = parse_seminar(CRRC_MESSAGE, date(2026, 9, 3))
            self.assertEqual(len(database.duplicates(duplicate)), 1)
            saved = database.get(item_id)
            self.assertIsNotNone(saved)
            assert saved is not None
            saved.location = "综合教学2号楼A201"
            database.update(saved)
            self.assertEqual(database.get(item_id).location, "综合教学2号楼A201")  # type: ignore[union-attr]
            self.assertEqual(len(database.history(date(2026, 9, 10))), 1)
            database.delete(item_id)
            self.assertEqual(database.all(), [])


if __name__ == "__main__":
    unittest.main()
