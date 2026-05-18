-- AI Tutor 项目完整数据库表结构
-- 包含所有表的创建语句

-- 用户表
CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `email` VARCHAR(100) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  UNIQUE KEY `uk_email` (`email`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 题目表
CREATE TABLE IF NOT EXISTS `questions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `content` TEXT NOT NULL,
  `answer` TEXT DEFAULT NULL,
  `difficulty` INT DEFAULT NULL,
  `knowledge_points` JSON DEFAULT NULL,
  `problem_type` VARCHAR(50) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_difficulty` (`difficulty`),
  KEY `idx_problem_type` (`problem_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 学习记录表
CREATE TABLE IF NOT EXISTS `learning_records` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `question_id` INT NOT NULL,
  `is_correct` BOOLEAN DEFAULT NULL,
  `user_answer` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_question_id` (`question_id`),
  KEY `idx_is_correct` (`is_correct`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_learning_record_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_learning_record_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 学生画图表
CREATE TABLE IF NOT EXISTS `user_profiles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `knowledge_mastery` JSON DEFAULT NULL,
  `weak_points` JSON DEFAULT NULL,
  `total_questions` INT DEFAULT 0,
  `correct_count` INT DEFAULT 0,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_id` (`user_id`),
  CONSTRAINT `fk_user_profile_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 聊天会话表
CREATE TABLE IF NOT EXISTS `chat_sessions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `session_name` VARCHAR(255) DEFAULT NULL,
  `start_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `end_time` DATETIME DEFAULT NULL,
  `status` VARCHAR(20) DEFAULT 'active',
  `total_messages` INT DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_start_time` (`start_time`),
  CONSTRAINT `fk_chat_session_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 聊天消息表
CREATE TABLE IF NOT EXISTS `chat_messages` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `session_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `role` ENUM('user', 'assistant') NOT NULL,
  `content` TEXT NOT NULL,
  `message_type` ENUM('text', 'image', 'file') DEFAULT 'text',
  `image_path` VARCHAR(500) DEFAULT NULL,
  `file_path` VARCHAR(500) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_solution` BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (`id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_role` (`role`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_is_solution` (`is_solution`),
  CONSTRAINT `fk_chat_message_session` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_chat_message_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 解题步骤表
CREATE TABLE IF NOT EXISTS `solution_steps` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `message_id` INT NOT NULL,
  `step_number` INT NOT NULL,
  `step_content` TEXT NOT NULL,
  `knowledge_point` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_message_id` (`message_id`),
  KEY `idx_step_number` (`step_number`),
  CONSTRAINT `fk_solution_step_message` FOREIGN KEY (`message_id`) REFERENCES `chat_messages` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 知识点表
CREATE TABLE IF NOT EXISTS `knowledge_points` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(100) NOT NULL,
  `description` TEXT DEFAULT NULL,
  `parent_id` INT DEFAULT NULL,
  `level` INT DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_name` (`name`),
  KEY `idx_parent_id` (`parent_id`),
  KEY `idx_level` (`level`),
  CONSTRAINT `fk_knowledge_point_parent` FOREIGN KEY (`parent_id`) REFERENCES `knowledge_points` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 题目-知识点关联表
CREATE TABLE IF NOT EXISTS `question_knowledge_points` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `question_id` INT NOT NULL,
  `knowledge_point_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_question_knowledge` (`question_id`, `knowledge_point_id`),
  KEY `idx_question_id` (`question_id`),
  KEY `idx_knowledge_point_id` (`knowledge_point_id`),
  CONSTRAINT `fk_qkp_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_qkp_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_points` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 学生-知识点掌握度表
CREATE TABLE IF NOT EXISTS `user_knowledge_mastery` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `knowledge_point_id` INT NOT NULL,
  `mastery_level` INT DEFAULT 0,
  `practice_count` INT DEFAULT 0,
  `correct_count` INT DEFAULT 0,
  `last_practiced_at` DATETIME DEFAULT NULL,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_knowledge` (`user_id`, `knowledge_point_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_knowledge_point_id` (`knowledge_point_id`),
  KEY `idx_mastery_level` (`mastery_level`),
  CONSTRAINT `fk_ukm_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ukm_knowledge_point` FOREIGN KEY (`knowledge_point_id`) REFERENCES `knowledge_points` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==================== V3 扩展字段 ====================

-- learning_records 表扩展
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `source_type` VARCHAR(50) NOT NULL DEFAULT 'recommended';
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `custom_question_data` JSON NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `ai_feedback` TEXT NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `recommendation_session_id` VARCHAR(100) NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `recommendation_algorithm_version` VARCHAR(50) NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `hint_count` INT DEFAULT 0;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `time_spent` INT NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `skip_reason` VARCHAR(20) NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `theta_before` FLOAT NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `theta_after` FLOAT NULL;
ALTER TABLE `learning_records` ADD COLUMN IF NOT EXISTS `mastery_updates` JSON NULL;

-- user_profiles 表扩展
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `theta_se` FLOAT NULL;
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `theta_ci_lower` FLOAT NULL;
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `theta_ci_upper` FLOAT NULL;
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `avg_mastery` FLOAT NULL;
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `weak_kp_count` INT DEFAULT 0;
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `learning_style` VARCHAR(20) NULL;
ALTER TABLE `user_profiles` ADD COLUMN IF NOT EXISTS `mastery_strategy` VARCHAR(20) DEFAULT 'simple';

-- user_knowledge_mastery 表扩展(BKT参数)
ALTER TABLE `user_knowledge_mastery` ADD COLUMN IF NOT EXISTS `p_guess` FLOAT DEFAULT 0.2;
ALTER TABLE `user_knowledge_mastery` ADD COLUMN IF NOT EXISTS `p_slip` FLOAT DEFAULT 0.1;
ALTER TABLE `user_knowledge_mastery` ADD COLUMN IF NOT EXISTS `p_known` FLOAT DEFAULT 0.5;
ALTER TABLE `user_knowledge_mastery` ADD COLUMN IF NOT EXISTS `consecutive_correct` INT DEFAULT 0;
ALTER TABLE `user_knowledge_mastery` ADD COLUMN IF NOT EXISTS `consecutive_wrong` INT DEFAULT 0;

-- ==================== V3 新增表 ====================

CREATE TABLE IF NOT EXISTS `user_ability_history` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `theta` FLOAT NOT NULL,
  `theta_se` FLOAT DEFAULT NULL,
  `theta_ci_lower` FLOAT DEFAULT NULL,
  `theta_ci_upper` FLOAT DEFAULT NULL,
  `avg_mastery` FLOAT DEFAULT NULL,
  `weak_kp_count` INT DEFAULT 0,
  `total_questions` INT DEFAULT 0,
  `correct_count` INT DEFAULT 0,
  `recorded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_time` (`user_id`, `recorded_at`),
  CONSTRAINT `fk_uah_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `mistake_book` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `question_id` INT NOT NULL,
  `error_count` INT DEFAULT 1,
  `first_error_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_error_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `mastered` BOOLEAN DEFAULT FALSE,
  `mastered_at` DATETIME DEFAULT NULL,
  `review_count` INT DEFAULT 0,
  `last_review_at` DATETIME DEFAULT NULL,
  `next_review_at` DATETIME DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_question` (`user_id`, `question_id`),
  KEY `idx_user_mastered` (`user_id`, `mastered`),
  KEY `idx_next_review` (`user_id`, `next_review_at`),
  CONSTRAINT `fk_mistake_book_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_mistake_book_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `favorites` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `question_id` INT NOT NULL,
  `folder_name` VARCHAR(50) NOT NULL DEFAULT '默认收藏夹',
  `note` TEXT DEFAULT NULL,
  `tags` JSON DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_question` (`user_id`, `question_id`),
  KEY `idx_user_folder` (`user_id`, `folder_name`),
  CONSTRAINT `fk_favorite_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_favorite_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_interaction_logs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `session_id` VARCHAR(100) DEFAULT NULL,
  `interaction_type` VARCHAR(50) NOT NULL,
  `question_id` INT DEFAULT NULL,
  `knowledge_points` JSON DEFAULT NULL,
  `difficulty` INT DEFAULT NULL,
  `content` TEXT DEFAULT NULL,
  `metadata` JSON DEFAULT NULL,
  `sentiment_tag` VARCHAR(20) DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_time` (`user_id`, `created_at`),
  KEY `idx_session` (`session_id`),
  CONSTRAINT `fk_interaction_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_interaction_question` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 初始化知识点数据（对齐 skill_tree.py 83节点知识图谱）
-- 专题1: 数列基础 (8)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('数列的概念与分类', '无法区分有穷/无穷数列、递增/递减/摆动/常数列', NULL, 1),
('数列的通项公式', '根据通项公式求指定项，通项公式是n的函数', NULL, 1),
('数列的递推关系', '递推关系需要首项+递推式才能确定数列', NULL, 1),
('数列的前n项和（Sn的概念）', 'Sn表示前n项和（而非第n项），Sn-S(n-1)求an时n≥2', NULL, 1),
('an与Sn的关系（由Sn求an）', '直接用Sn-S(n-1)=an却不验证n≥2', NULL, 2),
('数列的函数特性（单调性初步）', '不会将an视为n的函数f(n)来分析单调性', NULL, 2),
('作差法与作商法判断数列单调性', '混淆作差法与作商法的适用条件', NULL, 3),
('数列的周期性初步', '不会通过递推公式迭代找周期', NULL, 2);

-- 专题2: 等差数列 (12)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('等差数列的定义与判定', '判定时不知道需要验证an+1-an为常数对任意n成立', NULL, 1),
('等差数列的通项公式（基本量法）', '不会通过a1和d两个基本量建立方程组求通项', NULL, 2),
('等差中项', '不理解2b=a+c ⇔ a,b,c成等差的双向等价性', NULL, 2),
('等差数列的下标性质', '不会利用m+n=p+q⇒am+an=ap+aq化简条件', NULL, 3),
('等差数列的前n项和公式', '两个求和公式只会用一个，不会灵活选择', NULL, 2),
('等差数列片段和性质', '不知道Sm, S2m-Sm, S3m-S2m也成等差数列', NULL, 3),
('Sn/n的性质', '不知道{Sn/n}也是等差数列', NULL, 3),
('等差数列的设元技巧（对称设元）', '不会用a-d, a, a+d设元简化条件', NULL, 3),
('等差数列的最值问题', '求Sn最值时不会配方或不会用邻项法', NULL, 3),
('等差数列奇数项和与偶数项和', '不知道S奇/S偶与中间项的关系', NULL, 3),
('两个等差数列和之比（An/Bn型）', '不知道an/bn = A(2n-1)/B(2n-1)的转化公式', NULL, 4),
('等差数列与方程综合', '碰到三项成等差与方程根结合的问题无法下手', NULL, 3);

-- 专题3: 等比数列 (10)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('等比数列的定义与判定', '判定时忽略an≠0、q≠0的隐含条件', NULL, 1),
('等比数列的通项公式（基本量法）', '不会通过a1和q两个基本量建立方程组求通项', NULL, 2),
('等比中项', '不理解b²=ac ⇔ a,b,c成等比的等价关系', NULL, 2),
('等比数列的下标性质', '不知道m+n=p+q⇒am·an=ap·aq', NULL, 3),
('等比数列的前n项和公式（含q=1与q≠1分类讨论）', '忘记验证q=1的情况，这是最高频错误', NULL, 2),
('等比数列片段和性质', '不知道Sm, S2m-Sm, S3m-S2m也成等比数列', NULL, 3),
('等比数列的单调性判定', '不会根据a1的正负和q的范围分类判断单调性', NULL, 3),
('等比数列的设元技巧（对称设元）', '不会用a/q, a, aq设三项', NULL, 3),
('等比数列与对数/指数综合', '不会利用取对数将等比关系转化为等差关系', NULL, 3),
('等比数列的奇偶项和性质', 'q=-1时不会分析奇偶项和的特殊性质', NULL, 3);

-- 专题4: 递推数列求通项 (17)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('递推关系的识别与变形', '拿到递推式后不知从何入手变形', NULL, 1),
('累加法求通项（an+1-an=f(n)型）', '不会识别an+1-an=f(n)的形式', NULL, 2),
('累乘法求通项（an+1/an=f(n)型）', '不会识别an+1/an=f(n)的形式', NULL, 2),
('由Sn求an（an=Sn-Sn-1，n≥2分段讨论）', '直接写an=Sn-Sn-1而不分n=1与n≥2讨论', NULL, 2),
('待定系数法构造等比数列（an+1=pan+q型）', '不会设an+1+λ=p(an+λ)', NULL, 2),
('待定系数法构造等比数列（an+1=pan+q^n型）', '面对含q^n的递推式无法下手', NULL, 3),
('待定系数法构造等比数列（an+1=pan+kn+b型）', '面对含n一次式的递推无法消去一次项', NULL, 3),
('倒数变换法求通项', '面对分式型递推不知道取倒数', NULL, 2),
('对数变换法求通项（an+1=p·an^k型）', '面对指数型乘积递推不知道取对数', NULL, 3),
('根式构造法求通项', '面对含根号的递推式不会平方配凑', NULL, 3),
('不动点法求通项（分式线性递推型）', '不会将分式递推化为等比形式', NULL, 3),
('特征根法求通项（二阶线性递推型）', '不会建立特征方程x²-px-q=0', NULL, 3),
('由递推关系构造等差数列', '不会通过变形证明{bn}是等差数列', NULL, 2),
('由递推关系构造等比数列', '不会通过变形证明{bn}是等比数列', NULL, 2),
('联立递推方程组消元法', '面对联立递推的方程组不会消元', NULL, 3),
('由几何/函数/实际背景建立递推关系', '不会从实际情境中抽象出递推关系', NULL, 3),
('递推关系中的奇偶分类与分段递推', '面对n分奇偶的不同递推式无法分别处理', NULL, 2);

-- 专题5: 数列求和 (12)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('公式求和法（等差/等比/平方和/立方和/奇数和）', '只记住等差等比公式，其他常用求和直接放弃', NULL, 1),
('分组求和法（等差+等比混合/通项拆分）', '不会拆分为两个独立数列分别求和再合并', NULL, 2),
('分式裂项求和（基本型：1/[n(n+k)]类）', '不理解裂项后中间项相消的望远镜原理', NULL, 2),
('根式裂项求和', '面对根式分母不知道有理化分子后裂项', NULL, 3),
('指数型裂项求和', '面对含指数分母的分式不会构造裂项结构', NULL, 3),
('高阶裂项与待定系数裂项', '面对分母为三次式的分式不会待定系数反推', NULL, 3),
('错位相减法（等差×等比型差比数列求和）', '错位相减时对齐错误或不会整理结果', NULL, 2),
('倒序相加法', '不会识别首尾项和为定值的倒序相加场景', NULL, 2),
('奇偶分组求和法', '不会按奇数项/偶数项分别求和再合并', NULL, 3),
('分段求和法（绝对值/分段定义型）', '含绝对值的数列求和忘记先找正负分界点', NULL, 3),
('并项求和法（相邻项配对）', '不会利用an+an+1的简单规律配对求和', NULL, 3),
('数列求和与恒成立/参数范围综合', '求和后不会将结果转化为最值问题', NULL, 3);

-- 专题6: 数列的单调性、周期性与最值 (6)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('数列单调性的判定（作差法/作商法/函数法）', '三种方法选用不当', NULL, 2),
('函数背景法分析数列最值与单调性', '不会将an=f(n)延拓为f(x)后利用导数分析', NULL, 3),
('邻项比较法求数列最大/最小项', '不会利用an≥an+1且an≥an-1解出最大项下标', NULL, 3),
('周期数列的判定与求值', '不会利用模运算直接定位', NULL, 2),
('递增/递减数列的参数约束问题', '不会将an+1>an恒成立转化为参数范围', NULL, 3),
('数列单调性与不等式综合', '不会利用数列单调性证明不等式', NULL, 3);

-- 专题7: 数学归纳法 (5)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('数学归纳法的基本原理', '不理解n=k成立推n=k+1成立的逻辑链条', NULL, 1),
('第一数学归纳法证明等式（含数列通项/求和）', '归纳递推步骤中不知道如何利用归纳假设', NULL, 2),
('第二数学归纳法（强归纳法）', '不理解第二归纳法与第一归纳法的区别', NULL, 2),
('归纳-猜想-证明（完整路径）', '不会通过计算前几项归纳猜想通项公式', NULL, 3),
('数学归纳法证明数列不等式', '归纳递推中放缩方向错误', NULL, 3);

-- 专题8: 数列不等式与放缩法 (8)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('裂项放缩法证明和式不等式', '不会将不易求和的通项放缩为可裂项的形式', NULL, 3),
('伪等比放缩法（构造等比上界）', '不会通过构造an+1≤q·an放缩为等比级数和', NULL, 3),
('根式裂项放缩', '面对含根式的和式不等式无法构造裂项放缩结构', NULL, 4),
('奇偶性放缩法', '面对交错级数不会利用相邻项配对调整放缩', NULL, 4),
('迭代放缩法', '不会通过递推式迭代展开放缩每一项', NULL, 3),
('放缩法的精度控制与多级放缩', '放缩后超出目标范围时不会调整放缩起点', NULL, 4),
('柯西不等式在数列不等式中的应用', '不会将求和式重组为柯西不等式形式', NULL, 3),
('伯努利不等式与指数放缩', '不会利用(1+x)^n≥1+nx进行放缩', NULL, 3);

-- 专题9: 数列综合应用 (5)
INSERT INTO `knowledge_points` (`name`, `description`, `parent_id`, `level`) VALUES
('等差与等比数列综合（混合条件型）', '面对同时含有等差和等比条件的题目无从下手', NULL, 2),
('由数列构造新数列并证明等差/等比', '不会根据目标设新数列bn', NULL, 3),
('数列存在性问题与反证法', '不会用反证法证明某些项不存在', NULL, 2),
('数列与函数/导数综合', '不会利用导函数零点确定数列单调性转折点', NULL, 2),
('数列与不等式综合（无放缩，纯推理型）', '不会利用数列固有性质推导不等式关系', NULL, 3);
