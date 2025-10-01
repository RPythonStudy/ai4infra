###
# 파일명: src/R/logger.R
# 목적: R 로깅 프레임워크 제공
# 기능: 
#  - R용 로거 설정이지만 Python과 같이 .env에서 설정값을 읽도록 함
# 변경이력
#  - 2025-09-01: 최초 생성 (BenKorea)
###


library(logger)


# .env 환경변수 로드
if (!requireNamespace("dotenv", quietly = TRUE)) {
  install.packages("dotenv")
}
library(dotenv)
dotenv::load_dot_env(file = here::here(".env"))


# 환경변수 읽기 및 기본값

LOG_LEVEL <- toupper(Sys.getenv("LOG_LEVEL", "DEBUG"))
PROJECT_NAME <- Sys.getenv("PROJECT_NAME", "Template")
LOG_PATH <- Sys.getenv("LOG_PATH", "logs")
LOG_PATH <- gsub("\\{PROJECT_NAME\\}", PROJECT_NAME, LOG_PATH)

# 로그 디렉토리 체크
log_dir <- dirname(LOG_PATH)
if (!dir.exists(log_dir)) {
  stop(sprintf("로그 디렉토리가 없습니다: %s", log_dir))
}

# 로그 파일 경로
log_file <- file.path(LOG_PATH, paste0(PROJECT_NAME, ".log"))

# 콘솔/파일 동시 출력
log_appender(appender_tee(log_file))

# 포맷
log_layout(layout_glue_generator(
  format = '[{format(time, "%Y-%m-%d %H:%M:%S")}] [{toupper(level)}] [{PROJECT_NAME}] {msg}'
))

## Python과 함수명 통일: log_critical 래퍼 추가
log_critical <- function(msg) {
  log_fatal(msg)
}
# 레벨 설정
valid_levels <- c("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")
if (!LOG_LEVEL %in% valid_levels) LOG_LEVEL <- "DEBUG"
log_threshold(LOG_LEVEL)

log_info(sprintf("로깅 레벨: %s, 로그 경로: %s", LOG_LEVEL, log_file))

