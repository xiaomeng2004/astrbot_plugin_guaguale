# config_manager.py
import yaml
import os

class ConfigManager:
    def __init__(self, external_config=None):
        self.config_path = "./data/plugins/astrbot_plugin_guaguale/guacfg.yaml"
        self.external_config = external_config
        # self.initConfig()  # 初始化时自动加载配置 -> 由外部调用
        
    def initConfig(self):
        """ 读取并解析YAML配置文件或使用外部配置 """
        try:
            if self.external_config:
                # 使用外部传入的配置
                config = self.external_config
            else:
                # 检查配置文件是否存在
                if not os.path.exists(self.config_path):
                    self._create_default_config()  # 创建默认配置
                    
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) 
                
            # 参数映射到类属性
            
            # 确保数值类型正确
            try:
                self.prizes = [int(x) for x in config['lottery']['prizes']] # 刮刮乐价值
            except (ValueError, TypeError, KeyError):
                self.prizes = [0, 5, 10, 20, 50, 100]
                
            try:
                self.weights = [float(x) for x in config['lottery']['weights']] # 对应权重
            except (ValueError, TypeError, KeyError):
                self.weights = [70, 15, 10, 3, 1.6, 0.4]
                
            self.cost = config['lottery']['cost'] # 一张刮刮乐价格
            self.max_daily_scratch = config['lottery']['max_daily_scratch'] #每天刮奖次数，<=0无限次
            self.num = config['lottery']['num'] #一张刮刮乐有几次机会

            self.rob_cooldown = config['robbery']['cooldown']
            self.rob_success_rate = config['robbery']['success_rate']
            self.rob_base_amount = config['robbery']['base_amount']
            self.rob_max_ratio = config['robbery']['max_ratio']
            self.rob_penalty = config['robbery']['penalty']

            self.event_chance = config['events']['chance']

            # 添加货币单位配置
            self.currency_unit = config.get('currency', {}).get('unit', '元')
            
        except (FileNotFoundError, yaml.YAMLError) as e:
            print(f"配置加载失败: {str(e)}")
            raise

    def _create_default_config(self):
        """ 生成默认配置文件 """
        default_config = {
            'lottery': {
                'prizes': [0, 5, 10, 20, 50, 100],
                'weights': [70, 15, 10, 3, 1.6, 0.4],
                'cost': 25,
                'max_daily_scratch': 10,
                'num': 7
            },
            'robbery': {
                'cooldown': 300,
                'success_rate': 35,
                'base_amount': 30,
                'max_ratio': 0.2,
                'penalty': 50
            },
            'events': {
                'chance': 15
            }
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)         