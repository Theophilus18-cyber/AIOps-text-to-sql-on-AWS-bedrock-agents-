output "database_name" {
  description = "Glue catalog database name"
  value       = aws_glue_catalog_database.this.name
}

output "crawler_name" {
  description = "Glue crawler name"
  value       = aws_glue_crawler.this.name
}
