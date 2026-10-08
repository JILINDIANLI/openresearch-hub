from __future__ import annotations

import json

from sqlalchemy import select, update

from .core.security import hash_password
from .database.database import SessionLocal
from .database.models import Algorithm, Dataset, Demo, Model, Paper, Project, Resource, ResourceShowcase, ShowcaseResult, Tag, Tutorial, User


def seed_database() -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "kai.shen@openresearch.local"))
        if user is None:
            user = User(username="kai-shen", display_name="Kai Shen", email="kai.shen@openresearch.local", password_hash=hash_password("openresearch"), organization="Research Lab", bio="AI, UAV and intelligent optimization researcher.", research_fields="AI, UAV, Optimization", research_interests=json.dumps(["AI", "UAV", "Optimization"], ensure_ascii=False), role="ADMIN")
            db.add(user)
            db.flush()
        else:
            if user.username == "Kai Shen" and db.scalar(select(User).where(User.username == "kai-shen", User.id != user.id)) is None:
                user.username = "kai-shen"
            user.display_name = user.display_name or "Kai Shen"
            user.research_interests = user.research_interests or json.dumps(["AI", "UAV", "Optimization"], ensure_ascii=False)
        user.role = "ADMIN"
        db.flush()
        # V1 acceptance data predates user authentication. Keep it visible, but
        # give it an explicit legacy maintainer rather than leaving it ownerless.
        db.execute(update(Resource).where(Resource.author_id.is_(None)).values(author_id=user.id))
        tag_names = ["Deep Learning", "Computer Vision", "Robotics", "Unmanned Systems", "Reinforcement Learning", "UAV", "Optimization", "LLM", "Large Language Model", "Energy System", "Multi-Agent", "Time Series Forecasting"]
        tags = {}
        for name in tag_names:
            tag = db.scalar(select(Tag).where(Tag.name == name))
            if tag is None:
                tag = Tag(name=name, description=f"OpenResearch research field: {name}")
                db.add(tag)
            tags[name] = tag
        db.flush()
        resources = [
            ("YOLO-UAV", "model", "面向航拍场景的目标检测模型，支持小目标与复杂背景。", ["Computer Vision", "UAV"], {"framework": "PyTorch", "parameters": "36M", "task": "Object Detection", "model_url": "https://github.com/"}),
            ("Vision Transformer", "model", "用于视觉表征与分类任务的开放基线模型。", ["Deep Learning", "Computer Vision"], {"framework": "PyTorch", "parameters": "86M", "task": "Image Classification", "model_url": "https://github.com/"}),
            ("MAPPO Policy", "model", "面向多智能体协同决策的策略模型。", ["Reinforcement Learning", "Multi-Agent"], {"framework": "PyTorch", "parameters": "9M", "task": "Multi-Agent Control", "model_url": "https://github.com/"}),
            ("Transformer Forecasting", "model", "多变量时间序列预测基线。", ["Deep Learning", "Energy System"], {"framework": "JAX", "parameters": "112M", "task": "Forecasting", "model_url": "https://github.com/"}),
            ("UAV Detection Dataset", "dataset", "高分辨率航拍目标检测与多场景标注基准。", ["Computer Vision", "UAV"], {"name": "UAV Detection Dataset", "size": "18.4 GB", "format": "images + JSON", "download_count": 8200, "dataset_url": "https://huggingface.co/datasets/"}),
            ("Wind Power Dataset", "dataset", "多地区风电出力时序预测数据集。", ["Energy System", "Optimization"], {"name": "Wind Power Dataset", "size": "2.1 GB", "format": "CSV", "download_count": 5600, "dataset_url": "https://huggingface.co/datasets/"}),
            ("Image Dataset", "dataset", "面向开放场景视觉理解的图像数据集。", ["Computer Vision", "Deep Learning"], {"name": "Image Dataset", "size": "6.8 GB", "format": "WebDataset", "download_count": 3900, "dataset_url": "https://huggingface.co/datasets/"}),
            ("MAPPO", "algorithm", "多智能体近端策略优化算法实现。", ["Reinforcement Learning", "Multi-Agent"], {}),
            ("PPO", "algorithm", "稳定、易复现的策略梯度算法。", ["Reinforcement Learning", "Optimization"], {}),
            ("SAC", "algorithm", "面向连续控制的最大熵强化学习算法。", ["Reinforcement Learning", "Robotics"], {}),
            ("Differential Evolution", "algorithm", "面向连续优化问题的经典群体智能算法。", ["Optimization"], {}),
            ("Black-winged Kite Algorithm", "algorithm", "面向复杂优化任务的仿生智能优化算法。", ["Optimization"], {}),
            ("Multi-UAV Formation Control", "project", "以 MAPPO 为核心的多无人机协同编队控制与仿真验证。", ["UAV", "Robotics", "Reinforcement Learning"], {"leader": "Kai Shen", "members": ["Kai Shen", "Lena Wu"], "status": "published", "github_url": "https://github.com/", "paper_url": "https://doi.org/", "demo_url": "https://youtube.com/"}),
            ("AI Forecast System", "project", "覆盖预测、优化调度与不确定性量化的研究工程。", ["Energy System", "Optimization"], {"leader": "Kai Shen", "members": ["Kai Shen", "Ming Rao"], "status": "published", "github_url": "https://github.com/"}),
            ("Renewable Energy Forecast System", "project", "面向风电与光伏场景的预测、优化调度与不确定性量化工程。", ["Energy System", "Time Series Forecasting"], {"leader": "Kai Shen", "members": ["Kai Shen", "Ming Rao"], "status": "published", "github_url": "https://github.com/"}),
            ("Multi-Agent RL Paper", "paper", "面向协同智能系统的多智能体强化学习研究。", ["Reinforcement Learning", "Multi-Agent"], {"title": "Multi-Agent Reinforcement Learning for Cooperative Autonomy", "authors": ["Kai Shen", "Lena Wu"], "journal": "Open Research Journal", "year": 2026, "doi": "10.0000/openresearch.2026.001", "abstract": "A reproducible study of cooperative decision making."}),
            ("Transformer Paper", "paper", "面向时间序列预测的 Transformer 方法与可复现实验论文。", ["Deep Learning", "Time Series Forecasting"], {"title": "Transformer Methods for Reliable Time Series Forecasting", "authors": ["Kai Shen", "Ming Rao"], "journal": "Open Research Journal", "year": 2025, "doi": "10.0000/openresearch.2025.002", "abstract": "A reproducible Transformer baseline for multivariate energy forecasting."}),
            ("Multi-UAV Formation Demo", "demo", "多无人机编队控制的可视化验证演示。", ["UAV", "Robotics"], {"demo_url": "https://www.youtube.com/"}),
            ("OpenResearch Reproduction Tutorial", "tutorial", "从数据、代码到实验结果的科研复现教程。", ["Deep Learning", "Optimization"], {}),
            ("YOLO-UAV-Test", "model", "用于发布流程验收的无人机目标检测模型测试资源。", ["Computer Vision", "UAV"], {"framework": "PyTorch", "parameters": "12M", "task": "Object Detection", "model_url": "https://example.com/yolo-uav-test"}),
            ("UAV-Dataset-Test", "dataset", "用于发布流程验收的公开无人机数据集测试资源。", ["Computer Vision", "UAV"], {"size": "120 MB", "format": "JPEG + JSON", "task": "Object Detection", "download_url": "https://example.com/uav-dataset-test"}),
            ("OpenResearch-Test-Project", "project", "用于发布流程验收的科研项目测试资源。", ["Robotics", "UAV"], {"leader": "Kai Shen", "members": ["Kai Shen"], "github_url": "https://github.com/openresearch/test-project", "demo_url": "https://example.com/test-demo"}),
        ]
        research_fields = {
            "YOLO-UAV": "Computer Vision",
            "Vision Transformer": "Computer Vision",
            "MAPPO Policy": "Reinforcement Learning",
            "Transformer Forecasting": "Energy Systems",
            "UAV Detection Dataset": "Computer Vision",
            "Wind Power Dataset": "Energy Systems",
            "Image Dataset": "Computer Vision",
            "MAPPO": "Reinforcement Learning",
            "PPO": "Reinforcement Learning",
            "SAC": "Robotics",
            "Differential Evolution": "Optimization",
            "Black-winged Kite Algorithm": "Optimization",
            "Multi-UAV Formation Control": "Unmanned Systems",
            "AI Forecast System": "Energy Systems",
            "Renewable Energy Forecast System": "Energy Systems",
            "Multi-Agent RL Paper": "Reinforcement Learning",
            "Transformer Paper": "Energy Systems",
            "Multi-UAV Formation Demo": "Unmanned Systems",
            "OpenResearch Reproduction Tutorial": "AI & Deep Learning",
            "YOLO-UAV-Test": "Computer Vision",
            "UAV-Dataset-Test": "Computer Vision",
            "OpenResearch-Test-Project": "Unmanned Systems",
        }
        for title, resource_type, description, resource_tag_names, details in resources:
            resource = db.scalar(select(Resource).where(Resource.title == title))
            if resource is not None:
                resource.research_field = resource.research_field or research_fields.get(title)
                continue
            resource = Resource(title=title, resource_type=resource_type, description=description, author_id=user.id, stars=1200 if title == "MAPPO" else 320, downloads=8600 if resource_type == "model" else 4200, license="Apache-2.0", visibility="public", review_status="PUBLISHED", research_field=research_fields.get(title), details_json=json.dumps(details, ensure_ascii=False), tags=[tags[name] for name in resource_tag_names])
            db.add(resource)
            db.flush()
            if resource_type == "model":
                db.add(Model(resource_id=resource.id, framework=details.get("framework", ""), parameters=details.get("parameters", ""), task=details.get("task", ""), model_url=details.get("model_url")))
            elif resource_type == "dataset":
                download_url = details.get("dataset_url") or details.get("download_url")
                db.add(Dataset(resource_id=resource.id, name=details.get("name", title), size=details.get("size", ""), format=details.get("format", ""), task=details.get("task", ""), download_count=details.get("download_count", 0), dataset_url=download_url, download_url=download_url))
            elif resource_type == "algorithm":
                db.add(Algorithm(resource_id=resource.id, category=details.get("category", ""), difficulty=details.get("difficulty", ""), paper_url=details.get("paper_url"), code_url=details.get("code_url")))
            elif resource_type == "project":
                db.add(Project(resource_id=resource.id, leader=details.get("leader", ""), members=", ".join(details.get("members", [])), status=details.get("status", "published"), github_url=details.get("github_url"), paper_url=details.get("paper_url"), demo_url=details.get("demo_url")))
            elif resource_type == "paper":
                db.add(Paper(resource_id=resource.id, title=details.get("title", title), authors=", ".join(details.get("authors", [])), journal=details.get("journal"), year=details.get("year"), doi=details.get("doi"), abstract=details.get("abstract", "")))
            elif resource_type == "demo":
                db.add(Demo(resource_id=resource.id, video_url=details.get("video_url") or details.get("demo_url"), project_url=details.get("project_url"), duration=details.get("duration", "")))
            elif resource_type == "tutorial":
                db.add(Tutorial(resource_id=resource.id, difficulty=details.get("difficulty", ""), duration=details.get("duration", ""), content_url=details.get("content_url")))
        showcase_resource = db.scalar(select(Resource).where(Resource.title == "Black-winged Kite Algorithm"))
        if showcase_resource and db.scalar(select(ResourceShowcase).where(ResourceShowcase.resource_id == showcase_resource.id)) is None:
            showcase = ResourceShowcase(
                resource_id=showcase_resource.id,
                created_by=user.id,
                title="Enhanced Black-winged Kite Algorithm",
                is_featured=True,
                short_description="A research showcase for an optimization method with reproducible benchmark evidence.",
                abstract="## Overview\nEnhanced Black-winged Kite Algorithm (EBKA) is an optimization method designed for difficult nonlinear research problems.",
                research_background="Modern engineering optimization often involves competing objectives, constrained decision spaces, and expensive evaluations. EBKA provides an interpretable search strategy for these settings.",
                methodology="## Method\n- Adaptive exploration balances global and local search.\n- Candidate solutions are refined with a lightweight exploitation rule.\n- The evaluation pipeline records the configuration needed to reproduce every run.",
                contributions="1. A clearer exploration-to-exploitation transition.\n2. More stable convergence on representative benchmark functions.\n3. A reproducible experimental report linked to the resource, code and versions.",
                experiments="Experiments use CEC2020 benchmark functions and a constrained engineering scheduling scenario. Every experiment records population size, evaluation budget, random seed and stopping condition.",
                results_summary="EBKA reached competitive objective values with more stable convergence across repeated trials.",
                citation_text="Kai Shen. Enhanced Black-winged Kite Algorithm. OpenResearch Hub, 2026.",
                bibtex="@article{shen2026ebka,\n  title={Enhanced Black-winged Kite Algorithm},\n  author={Shen, Kai},\n  year={2026},\n  journal={OpenResearch Hub}\n}",
            )
            db.add(showcase)
            db.flush()
            db.add(ShowcaseResult(
                showcase_id=showcase.id,
                title="Benchmark comparison",
                description="Representative mean objective values from repeated optimization runs.",
                table_data=[
                    {"algorithm": "EBKA", "mean_cost": 100.2, "stability": "High"},
                    {"algorithm": "BKA", "mean_cost": 104.8, "stability": "Medium"},
                    {"algorithm": "DE", "mean_cost": 109.1, "stability": "Medium"},
                ],
            ))
        db.commit()
