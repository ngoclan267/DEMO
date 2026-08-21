-- Chạy tự động khi container Postgres khởi tạo lần đầu (chỉ khi volume dữ liệu trống).
-- Tạo thêm DB "painpoints_test" dùng riêng cho tests/test_db/test_models.py, tách biệt với DB
-- "painpoints" chứa dữ liệu dev thật (seed + crawl) để chạy pytest không xóa mất dữ liệu dev.
CREATE DATABASE painpoints_test;
