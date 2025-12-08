-- Add transformChain column to routes table
ALTER TABLE `routes` ADD COLUMN `transform_chain` TEXT NULL;
